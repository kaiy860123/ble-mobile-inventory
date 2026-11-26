import {CognitoIdentityProviderClient,InitiateAuthCommand,RespondToAuthChallengeCommand} from '@aws-sdk/client-cognito-identity-provider';
import {CognitoIdentityClient,GetIdCommand,GetCredentialsForIdentityCommand} from '@aws-sdk/client-cognito-identity';
import {SignatureV4} from '@smithy/signature-v4';
import {HttpRequest} from '@smithy/protocol-http';
import {Sha256} from '@aws-crypto/sha256-js';
import {formatUrl} from '@aws-sdk/util-format-url';
import mqtt from 'mqtt';

export class CloudSession {
  constructor(config,onState,onStatus){this.config=config;this.onState=onState;this.onStatus=onStatus;this.auth=new CognitoIdentityProviderClient({region:config.region});this.identity=new CognitoIdentityClient({region:config.region});this.client=null;this.refreshTimer=null;this.generation=0;}
  async login(username,password,newPassword){
    let result;
    if(this.challenge){
      result=await this.auth.send(new RespondToAuthChallengeCommand({ClientId:this.config.userPoolClientId,ChallengeName:'NEW_PASSWORD_REQUIRED',Session:this.challenge.Session,ChallengeResponses:{USERNAME:this.challenge.username,NEW_PASSWORD:newPassword}}));
    }else result=await this.auth.send(new InitiateAuthCommand({ClientId:this.config.userPoolClientId,AuthFlow:'USER_PASSWORD_AUTH',AuthParameters:{USERNAME:username,PASSWORD:password}}));
    if(result.ChallengeName==='NEW_PASSWORD_REQUIRED'){this.challenge={...result,username:result.ChallengeParameters?.USER_ID_FOR_SRP??username};return {newPasswordRequired:true};}
    if(!result.AuthenticationResult?.IdToken) throw new Error('此帳號驗證流程尚不支援，請由管理者檢查帳號設定。');
    this.challenge=null;this.tokens=result.AuthenticationResult;this.expiresAt=Date.now()+(this.tokens.ExpiresIn??3600)*1000;
    await this.connect();return {success:true};
  }
  async credentials(){
    const provider=`cognito-idp.${this.config.region}.amazonaws.com/${this.config.userPoolId}`;
    const Logins={[provider]:this.tokens.IdToken};
    const {IdentityId}=await this.identity.send(new GetIdCommand({IdentityPoolId:this.config.identityPoolId,Logins}));
    this.identityId=IdentityId;
    const result=await this.identity.send(new GetCredentialsForIdentityCommand({IdentityId,Logins}));
    if(!result.Credentials) throw new Error('無法取得臨時觀看權限。');
    return {accessKeyId:result.Credentials.AccessKeyId,secretAccessKey:result.Credentials.SecretKey,sessionToken:result.Credentials.SessionToken};
  }
  async connect(){
    const generation=++this.generation;
    clearTimeout(this.refreshTimer);
    this.client?.end(true);
    this.onStatus('connecting','正在取得即時觀看權限');
    const credentials=await this.credentials();
    const signer=new SignatureV4({credentials,region:this.config.region,service:'iotdevicegateway',sha256:Sha256});
    const signed=await signer.presign(new HttpRequest({protocol:'wss:',hostname:this.config.endpoint,method:'GET',path:'/mqtt',headers:{host:this.config.endpoint}}),{expiresIn:300});
    if(generation!==this.generation)return;
    const clientId='viewer-'+crypto.randomUUID();
    this.client=mqtt.connect(formatUrl(signed),{clientId,protocolVersion:4,clean:true,reconnectPeriod:0,connectTimeout:15000,keepalive:30});
    this.client.on('connect',()=>{if(generation!==this.generation)return;this.client.subscribe(this.config.topic,{qos:0},(error,grants)=>{if(error||grants?.some(g=>g.qos===128))this.onStatus('error','觀看權限未就緒，請確認管理者已完成帳號授權。');else this.onStatus('connected','已連線，等待 RPi 發布資料');});});
    this.client.on('message',(_topic,payload)=>{try{const state=JSON.parse(payload.toString());if(state.schema_version==='1.0'&&Array.isArray(state.devices)&&state.scanner&&Number.isFinite(state.timestamp))this.onState(state);}catch{this.onStatus('error','收到無法辨識的即時資料');}});
    this.client.on('error',()=>{if(generation===this.generation)this.onStatus('error','AWS 連線失敗，請確認帳號授權及網路。');});
    this.client.on('close',()=>{if(generation!==this.generation)return;this.onStatus('disconnected','即時連線中斷，正在重連');clearTimeout(this.refreshTimer);this.refreshTimer=setTimeout(()=>this.reconnect(),5000);});
    const expires=Math.max(10000,this.expiresAt-Date.now()-120000);
    this.refreshTimer=setTimeout(()=>this.reconnect(true),expires);
  }
  async reconnect(refresh=false){
    try{
      if((refresh||Date.now()>this.expiresAt-120000)&&this.tokens?.RefreshToken){const result=await this.auth.send(new InitiateAuthCommand({ClientId:this.config.userPoolClientId,AuthFlow:'REFRESH_TOKEN_AUTH',AuthParameters:{REFRESH_TOKEN:this.tokens.RefreshToken}}));this.tokens={...this.tokens,...result.AuthenticationResult};this.expiresAt=Date.now()+(result.AuthenticationResult.ExpiresIn??3600)*1000;}
      await this.connect();
    }catch{this.onStatus('error','觀看憑證已失效，請重新登入。');}
  }
  logout(){++this.generation;clearTimeout(this.refreshTimer);this.client?.end(true);this.client=null;this.tokens=null;this.challenge=null;this.onStatus('disconnected','已登出');}
}
