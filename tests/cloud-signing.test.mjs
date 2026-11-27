import test from 'node:test';
import assert from 'node:assert/strict';
import {signedIotWebsocketUrl} from '../web/cloud.js';

test('IoT STS token is transported but does not change the canonical signature',async()=>{
  const config={region:'ap-southeast-2',endpoint:'example-ats.iot.ap-southeast-2.amazonaws.com'};
  const credentials={accessKeyId:'EXAMPLEKEY',secretAccessKey:'example-secret'};
  const date=new Date('2026-11-27T09:00:00Z');
  const plain=new URL(await signedIotWebsocketUrl(config,credentials,date));
  const first=new URL(await signedIotWebsocketUrl(config,{...credentials,sessionToken:'token+/one='},date));
  const second=new URL(await signedIotWebsocketUrl(config,{...credentials,sessionToken:'token/two+='},date));
  assert.equal(first.searchParams.get('X-Amz-Security-Token'),'token+/one=');
  assert.equal(second.searchParams.get('X-Amz-Security-Token'),'token/two+=');
  assert.equal(first.searchParams.get('X-Amz-Signature'),plain.searchParams.get('X-Amz-Signature'));
  assert.equal(second.searchParams.get('X-Amz-Signature'),plain.searchParams.get('X-Amz-Signature'));
  assert.equal(plain.searchParams.has('X-Amz-Security-Token'),false);
  assert.equal(first.protocol,'wss:');
  assert.equal(first.pathname,'/mqtt');
  assert.equal(first.searchParams.get('X-Amz-Expires'),'300');
});
