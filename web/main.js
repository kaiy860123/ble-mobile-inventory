import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {qualityLabels,finite,number,validateReplay,allDevices,secondsLabel,csvFromFrames} from './state.js';
const $=id=>document.getElementById(id);
const text=(id,value)=>{$(id).textContent=String(value);};
let frame=null,mode='replay',bootstrap=null,cloudConfig=null,cloudSession=null,localSocket=null,reconnectTimer=null,lastReceived=0;
let replay=null,replayIndex=0,playTimer=null,selectedId='T01',mapMode='grid',leaflet=null,mapLayer=null,trail=[],localGeneration=0,selectionSignature='',lastRun=null,cloudPending=false;
let localView={zoom:1,x:0,y:0},dragStart=null,localCanvasHeight=450;
const roleLabels={anchor:'固定 Anchor',target:'待定位 Target',scanner:'移動掃描器'};
function notice(message,warning=false){text('notice',message);$('notice').classList.toggle('warning',warning);}
function connection(message,connected=false){text('connection',message);$('connection').classList.toggle('connected',connected);}
function formatTime(timestamp){return finite(timestamp)?new Date(timestamp*1000).toLocaleTimeString('zh-TW',{hour12:false}):'—';}
function el(tag,content,className){const node=document.createElement(tag);if(content!==undefined)node.textContent=String(content);if(className)node.className=className;return node;}
function sourceLabel(){return `${mode==='replay'?'回放 · ':''}${frame?.source==='physical'?'實體 BLE':'模擬觀測'}${frame?.input_mode==='demo'?' · 合成示範':''}`;}
function render(){
  if(!frame)return;
  const devices=allDevices(frame),targets=frame.devices.filter(d=>d.role==='target');
  if(lastRun!==frame.run_id){trail=[];lastRun=frame.run_id;}
  const point=frame.scanner.position;
  if(point&&frame.scanner.quality==='valid'&&(!trail.length||trail.at(-1).timestamp!==frame.scanner.position_at))trail.push({timestamp:frame.scanner.position_at,...point});
  trail=trail.slice(-600);
  text('count-total',frame.counts.inventoried);text('count-visible',frame.counts.visible);text('count-located',targets.filter(d=>d.position&&d.quality==='valid').length);
  text('count-total-note',`本次預期 ${frame.counts.expected} 個 Target · 依 ID 去重`);
  text('quality-note',frame.scanner.quality==='valid'?`掃描器測距殘差 ${number(point?.residual_m)} m`:'等待有效的 Anchor 定位');
  text('source-badge',sourceLabel());text('task-status',frame.active?'巡查進行中':'巡查已結束');
  text('run-label',`任務 ${frame.run_id} · ${formatTime(frame.timestamp)}`);
  text('frame-label',`${frame.site.frame_id} · 單位公尺`);
  const geo=frame.site.georeference;
  text('coordinate-status',geo?`已地理對準${geo.source==='example'?' · 範例原點':''} · 旋轉 ${geo.rotation_deg??0}°`:'尚未地理對準');
  $('start-task').disabled=mode!=='local'||!bootstrap;
  $('stop-task').disabled=mode!=='local'||!bootstrap||!frame.active;
  $('replay-panel').hidden=mode!=='replay';
  $('source-select').value=mode;
  $('geo-button').disabled=!devices.some(d=>d.position?.wgs84);
  if(mapMode==='geo'&&$('geo-button').disabled)setMapMode('grid');
  renderMap();renderDevices(devices);renderDetail(devices);
}
function svg(tag,attrs={},content){const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs))node.setAttribute(k,String(v));if(content!==undefined)node.textContent=String(content);return node;}
function renderMap(){
  if(!frame)return;
  if(mapMode==='geo'){renderGeo();return;}
  const root=$('local-map');root.replaceChildren();
  const rect=root.getBoundingClientRect(),uiScale=800/Math.max(rect.width,1);localCanvasHeight=800*Math.max(rect.height,1)/Math.max(rect.width,1);
  root.setAttribute('viewBox',`${localView.x} ${localView.y} ${800/localView.zoom} ${localCanvasHeight/localView.zoom}`);
  const [xmin,ymin,xmax,ymax]=frame.site.bounds_m,w=xmax-xmin,h=ymax-ymin;
  const scale=Math.min((800-110*uiScale)/w,(localCanvasHeight-105*uiScale)/h),left=(800-w*scale)/2,top=(localCanvasHeight-h*scale)/2-8*uiScale;
  const pos=p=>[left+(p.x_m-xmin)*scale,top+(ymax-p.y_m)*scale];
  const border=svg('rect',{x:left,y:top,width:w*scale,height:h*scale,fill:'#f4f8fd',stroke:'#dce6f3','stroke-dasharray':'4 5',rx:3});root.append(border);
  const step=Math.max(1,Math.ceil(Math.max(w,h)/Math.max(3,Math.floor(rect.width/45))));
  for(let x=Math.ceil(xmin/step)*step;x<=xmax;x+=step){const sx=left+(x-xmin)*scale;root.append(svg('line',{x1:sx,y1:top,x2:sx,y2:top+h*scale,stroke:'#e3ebf6','stroke-width':uiScale}));root.append(svg('text',{x:sx,y:top+h*scale+22*uiScale,fill:'#91a1b8','font-size':11*uiScale,'text-anchor':'middle'},number(x,0)));}
  for(let y=Math.ceil(ymin/step)*step;y<=ymax;y+=step){const sy=top+(ymax-y)*scale;root.append(svg('line',{x1:left,y1:sy,x2:left+w*scale,y2:sy,stroke:'#e3ebf6','stroke-width':uiScale}));root.append(svg('text',{x:left-13*uiScale,y:sy+4*uiScale,fill:'#91a1b8','font-size':11*uiScale,'text-anchor':'end'},number(y,0)));}
  root.append(svg('text',{x:left+w*scale+18*uiScale,y:top+h*scale+4*uiScale,fill:'#9cacbf','font-size':11*uiScale},'X'));
  root.append(svg('text',{x:left-4*uiScale,y:top-15*uiScale,fill:'#9cacbf','font-size':11*uiScale},'Y'));
  if($('trail-toggle').checked&&trail.length>1)root.append(svg('polyline',{points:trail.map(p=>pos(p).join(',')).join(' '),fill:'none',stroke:'#729cea','stroke-width':2*uiScale,'stroke-dasharray':'4 5',opacity:.7}));
  for(const d of allDevices(frame)){
    if(!d.position||!finite(d.position.x_m)||!finite(d.position.y_m))continue;
    const [x,y]=pos(d.position);const selected=d.id===selectedId,stale=!['valid','fixed'].includes(d.quality);
    const color=stale?'#9aa9be':d.role==='anchor'?'#14a0b2':d.role==='scanner'?'#2463eb':'#e6a13b';
    const g=svg('g',{tabindex:0,role:'button','aria-label':`選取 ${d.id}`,'data-device-id':d.id,style:'cursor:pointer'});
    if(selected)g.append(svg('circle',{cx:x,cy:y,r:22*uiScale,fill:color,opacity:.09}));
    if(d.role==='anchor')g.append(svg('rect',{x:x-5*uiScale,y:y-5*uiScale,width:10*uiScale,height:10*uiScale,rx:2*uiScale,fill:color,stroke:'white','stroke-width':2*uiScale}));
    else{g.append(svg('circle',{cx:x,cy:y,r:(d.role==='scanner'?17:12)*uiScale,fill:color,opacity:.13}));g.append(svg('circle',{cx:x,cy:y,r:(d.role==='scanner'?7:6)*uiScale,fill:color,stroke:'white','stroke-width':2*uiScale}));}
    const label=svg('text',{x,y:y-21*uiScale,'text-anchor':'middle',fill:d.role==='scanner'?'#3970c8':'#6d7e98','font-size':14*uiScale,'font-weight':selected?650:500},d.id);g.append(label);
    g.addEventListener('click',()=>selectDevice(d.id));g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' ')selectDevice(d.id);});root.append(g);
  }
}
function renderGeo(){
  if(!leaflet){leaflet=L.map('geo-map',{zoomControl:true});L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:20,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).on('tileerror',()=>notice('底圖載入失敗；設備資料仍保留，可切回 Local 網格。',true)).addTo(leaflet);mapLayer=L.layerGroup().addTo(leaflet);}
  mapLayer.clearLayers();const points=[];
  for(const d of allDevices(frame)){const g=d.position?.wgs84;if(!g)continue;const p=[g.latitude_deg,g.longitude_deg];points.push(p);const color=!['valid','fixed'].includes(d.quality)?'#9aa9be':d.role==='anchor'?'#14a0b2':d.role==='scanner'?'#2463eb':'#e6a13b';const label=el('span',d.id);L.circleMarker(p,{radius:d.id===selectedId?9:6,color:'#fff',weight:2,fillColor:color,fillOpacity:1}).bindTooltip(label).on('click',()=>selectDevice(d.id)).addTo(mapLayer);}
  if($('trail-toggle').checked){const path=trail.filter(p=>p.wgs84).map(p=>[p.wgs84.latitude_deg,p.wgs84.longitude_deg]);if(path.length>1)L.polyline(path,{color:'#729cea',weight:2}).addTo(mapLayer);}
  if(points.length&&!leaflet._fieldInitialized){leaflet.fitBounds(points,{padding:[35,35],maxZoom:19});leaflet._fieldInitialized=true;}
  setTimeout(()=>leaflet.invalidateSize(),0);
}
function setMapMode(value){mapMode=value;$('local-map').style.display=value==='grid'?'block':'none';$('geo-map').hidden=value!=='geo';$('grid-button').classList.toggle('selected',value==='grid');$('geo-button').classList.toggle('selected',value==='geo');renderMap();}
function selectDevice(id){selectedId=id;render();}
function statusNode(d){return el('span',d.role==='scanner'?(d.quality==='valid'?'位置有效':'等待觀測'):d.visible?'接收中':d.last_seen?'暫未收到':'尚未偵測','status '+(d.visible?'good':d.last_seen?'warn':''));}
function renderDevices(devices){
  const tbody=$('device-rows');tbody.replaceChildren();text('device-count',devices.length);
  for(const d of devices){const tr=el('tr',undefined,d.id===selectedId?'selected':'');tr.tabIndex=0;tr.addEventListener('click',()=>selectDevice(d.id));tr.addEventListener('keydown',e=>{if(e.key==='Enter')selectDevice(d.id);});const id=el('td');const wrap=el('span',undefined,'id-cell');wrap.append(el('i',undefined,`id-dot ${d.role}`),el('span',d.id));id.append(wrap);const state=el('td');state.append(statusNode(d));const quality=el('td');quality.append(el('span',qualityLabels[d.quality]??'未知',`status ${['valid','fixed'].includes(d.quality)?'good':'warn'}`));
    tr.append(id,el('td',roleLabels[d.role]??d.role),state,el('td',finite(d.rssi_dbm)?`${number(d.rssi_dbm,0)} dBm`:'—'),el('td',d.position?`${number(d.position.x_m)}, ${number(d.position.y_m)}`:'—'),quality,el('td',formatTime(d.last_seen)));tbody.append(tr);}
}
function renderDetail(devices){
  const d=devices.find(d=>d.id===selectedId)??devices.find(d=>d.role==='target')??devices[0];if(!d)return;selectedId=d.id;
  const box=$('device-detail');box.replaceChildren();const heading=el('div',undefined,'detail-title');const description=el('div');description.append(el('h3',d.id),el('p',roleLabels[d.role]??d.role));heading.append(el('div',d.role==='target'?'T':d.role==='anchor'?'A':'R','detail-monogram'),description);box.append(heading);
  const list=el('dl',undefined,'detail-list');const p=d.position,g=p?.wgs84;const entries=[['接收狀態',d.visible?'接收中':d.last_seen?'暫未收到':'等待觀測'],['定位品質',qualityLabels[d.quality]??'未知'],['RSSI',finite(d.rssi_dbm)?`${number(d.rssi_dbm,0)} dBm`:'—'],['Local X / Y',p?`${number(p.x_m)} / ${number(p.y_m)} m`:'—'],['WGS84 緯度',g?number(g.latitude_deg,7):'尚未地理對準'],['WGS84 經度',g?number(g.longitude_deg,7):'尚未地理對準'],['測距殘差',finite(p?.residual_m)?`${number(p.residual_m)} m`:'—'],['定位時間',formatTime(d.position_at)]];
  for(const [key,value]of entries){const row=el('div');row.append(el('dt',key),el('dd',value,key.includes('Local')?'coord-value':''));list.append(row);}box.append(list,el('p',d.reason||'有效估計；測距殘差不代表真實位置誤差。','detail-reason'));
}
function onFrame(value){frame=value;lastReceived=Date.now();render();if(mode==='local'){connection('本地資料連線中',true);notice(frame.input_error||`${frame.input_mode==='demo'?'合成示範觀測（非 Gazebo／實機測試）':'本地即時觀測'} · 本地紀錄持續保存${frame.cloud?.enabled?frame.cloud.connected?' · AWS 已連線':' · AWS 未連線，本地繼續':''}`,Boolean(frame.input_error));}else if(mode==='cloud'){connection('AWS 資料連線中',true);notice('已登入 · 即時資料唯讀 · 巡查由現場 RPi 操作');}}
function pauseReplay(){clearTimeout(playTimer);playTimer=null;text('play-button','播放');}
function showReplay(index){if(!replay)return;replayIndex=Math.min(Math.max(0,index),replay.frames.length-1);frame=replay.frames[replayIndex];trail=[];lastRun=frame.run_id;for(const f of replay.frames.slice(Math.max(0,replayIndex-600),replayIndex+1))if(f.scanner?.quality==='valid'&&f.scanner.position)trail.push({timestamp:f.scanner.position_at,...f.scanner.position});$('replay-slider').value=String(replayIndex);text('replay-time',secondsLabel(frame.timestamp-replay.frames[0].timestamp));render();}
function playNext(){if(!replay)return;if(replayIndex>=replay.frames.length-1){pauseReplay();return;}const delay=Math.max(20,(replay.frames[replayIndex+1].timestamp-replay.frames[replayIndex].timestamp)*1000/Number($('playback-speed').value));playTimer=setTimeout(()=>{showReplay(replayIndex+1);playNext();},delay);}
function disconnectLocal(){++localGeneration;clearTimeout(reconnectTimer);localSocket?.close();localSocket=null;}
function loadReplay(value,label='匯入實驗紀錄'){
  replay=validateReplay(value);pauseReplay();disconnectLocal();cloudSession?.logout();mode='replay';$('replay-slider').max=String(replay.frames.length-1);text('replay-description',`${label} · ${replay.frames.length} 個影格`);text('replay-duration',secondsLabel(replay.frames.at(-1).timestamp-replay.frames[0].timestamp));showReplay(Math.min(15,replay.frames.length-1));connection('紀錄回放');notice(`${label} · ${replay.frames[0].source==='physical'?'實體紀錄':'模擬紀錄'}，此畫面不是即時資料。`);text('cloud-button','登入即時資料');
}
async function loadDemo(){const response=await fetch('./demo.json');if(!response.ok)throw new Error('尚無示範資料，請先執行範例產生腳本。');loadReplay(await response.json(),'合成示範回放（非 Gazebo／實機）');}
async function connectLocal(){
  const response=await fetch('./api/bootstrap',{cache:'no-store'});if(!response.ok)throw new Error('此網址沒有 RPi 本地服務，請開啟 RPi 網址或使用 AWS 即時模式。');bootstrap=await response.json();if(!bootstrap.local)throw new Error('無效的本地服務。');
  pauseReplay();cloudSession?.logout();disconnectLocal();mode='local';const generation=localGeneration;
  const connect=()=>{if(mode!=='local'||generation!==localGeneration)return;const url=new URL('./api/ws',location.href);url.protocol=location.protocol==='https:'?'wss:':'ws:';localSocket=new WebSocket(url);localSocket.onmessage=event=>{try{onFrame(JSON.parse(event.data));}catch{notice('無法讀取本地資料。',true);}};localSocket.onclose=()=>{if(mode==='local'&&generation===localGeneration){connection('本地連線中斷');notice('本地網頁連線中斷，位置為最後收到的資料；正在重新連線。',true);reconnectTimer=setTimeout(connect,2000);}};};connect();
}
async function control(action,extra={}){try{const response=await fetch('./api/control',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':bootstrap.control_token},body:JSON.stringify({action,...extra})});if(!response.ok)throw new Error(await response.text());onFrame(await response.json());}catch(error){notice(error.message,true);}}
function download(contents,type,name){const url=URL.createObjectURL(new Blob([contents],{type}));const a=el('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function exportData(format){
  if(mode==='local'){const response=await fetch(`./api/export?format=${format}`);if(!response.ok){notice('匯出失敗。',true);return;}download(await response.text(),format==='csv'?'text/csv':'application/json',`${frame.run_id}.${format==='csv'?'csv':'json'}`);return;}
  if(mode==='cloud'){notice('完整紀錄保存在 RPi，請由本地頁面匯出；AWS 即時通道不保存歷史。',true);return;}
  if(!replay)return;download(format==='csv'?csvFromFrames(replay.frames):JSON.stringify(replay),format==='csv'?'text/csv':'application/json',`${frame.run_id}.${format==='csv'?'csv':'json'}`);
}
$('grid-button').onclick=()=>setMapMode('grid');$('geo-button').onclick=()=>setMapMode('geo');$('trail-toggle').onchange=renderMap;$('fit-map').onclick=()=>{localView={zoom:1,x:0,y:0};if(leaflet)leaflet._fieldInitialized=false;renderMap();};
$('local-map').addEventListener('wheel',event=>{event.preventDefault();const rect=$('local-map').getBoundingClientRect(),old=localView.zoom,next=Math.max(.5,Math.min(4,old*Math.exp(-event.deltaY*.001)));localView.x+=(800/old-800/next)*(event.clientX-rect.left)/rect.width;localView.y+=(localCanvasHeight/old-localCanvasHeight/next)*(event.clientY-rect.top)/rect.height;localView.zoom=next;renderMap();},{passive:false});
$('local-map').addEventListener('pointerdown',event=>{if(event.target.closest('[data-device-id]'))return;dragStart={clientX:event.clientX,clientY:event.clientY,x:localView.x,y:localView.y};$('local-map').setPointerCapture(event.pointerId);});
$('local-map').addEventListener('pointermove',event=>{if(!dragStart)return;const rect=$('local-map').getBoundingClientRect();localView.x=dragStart.x-(event.clientX-dragStart.clientX)*800/rect.width/localView.zoom;localView.y=dragStart.y-(event.clientY-dragStart.clientY)*localCanvasHeight/rect.height/localView.zoom;renderMap();});
$('local-map').addEventListener('pointerup',()=>{dragStart=null;});$('local-map').addEventListener('pointercancel',()=>{dragStart=null;});
$('start-task').onclick=()=>control('start');$('stop-task').onclick=()=>control('stop');
$('export-json').onclick=()=>exportData('json');$('export-csv').onclick=()=>exportData('csv');
$('import-button').onclick=()=>$('replay-file').click();$('nav-replay').onclick=()=>$('replay-file').click();
$('replay-file').onchange=async event=>{try{const file=event.target.files[0];if(!file)return;if(file.size>50*1024*1024)throw new Error('回放檔案上限為 50 MB。');loadReplay(JSON.parse(await file.text()),file.name);}catch(error){notice(error.message,true);}finally{event.target.value='';}};
$('load-demo').onclick=()=>loadDemo().catch(error=>notice(error.message,true));
$('play-button').onclick=()=>{if(playTimer)pauseReplay();else{if(replayIndex>=replay.frames.length-1)showReplay(0);text('play-button','暫停');playNext();}};
$('replay-slider').oninput=event=>{pauseReplay();showReplay(Number(event.target.value));};
$('source-select').onchange=async event=>{const selected=event.target.value;try{if(selected==='local')await connectLocal();else if(selected==='replay'){if(replay)loadReplay(replay,'實驗回放');else await loadDemo();}else $('cloud-button').click();}catch(error){notice(error.message,true);}event.target.value=mode;};
$('cloud-button').onclick=()=>{if(mode==='cloud'&&cloudSession?.tokens){cloudSession.logout();text('cloud-button','登入即時資料');connection('已登出');notice('已登出；畫面保留最後收到的狀態，非即時資料。',true);return;}text('login-error',cloudConfig?'':'此網站尚未配置 AWS 連線。部署設定完成後即可登入；目前可使用本地或回放。');$('login-dialog').showModal();};
$('cancel-login').onclick=()=>$('login-dialog').close();
$('login-form').onsubmit=async event=>{
  event.preventDefault();if(!cloudConfig){text('login-error','尚未配置 AWS 連線，請先完成雲端部署。');return;}
  $('login-submit').disabled=true;text('login-error','');
  try{
    if(!cloudSession){const {CloudSession}=await import('./cloud.js');cloudSession=new CloudSession(cloudConfig,state=>{mode='cloud';cloudPending=false;onFrame(state);},(status,message)=>{if(mode==='cloud'||cloudPending){connection(message,status==='connected');if(status!=='connected')notice(message,true);}});}
    cloudPending=true;
    const result=await cloudSession.login($('username').value.trim(),$('password').value,$('new-password').value);
    if(result.newPasswordRequired){$('new-password-label').hidden=false;$('new-password').required=true;text('login-error','請設定新密碼後再次送出。');return;}
    disconnectLocal();pauseReplay();mode='cloud';trail=[];lastRun=null;lastReceived=Date.now();$('source-select').value=mode;$('start-task').disabled=true;$('stop-task').disabled=true;$('replay-panel').hidden=true;text('cloud-button','登出即時資料');$('login-dialog').close();$('password').value='';$('new-password').value='';notice('已登入 AWS；等待 RPi 發布最新狀態。目前畫面在收到資料前仍為上次紀錄。');
  }catch(error){cloudPending=false;text('login-error',error.name==='NotAuthorizedException'?'帳號或密碼不正確。':error.name==='UserNotFoundException'?'找不到觀看帳號。':error.message??'登入失敗。');}finally{$('login-submit').disabled=false;}
};
setInterval(()=>{if((mode==='local'||mode==='cloud')&&lastReceived&&Date.now()-lastReceived>10000){connection('即時資料中斷');notice('超過 10 秒未收到新資料；目前顯示最後收到的狀態。',true);}},1000);
window.addEventListener('resize',renderMap);
async function init(){try{const response=await fetch('./cloud-config.json',{cache:'no-store'});if(response.ok){const value=await response.json();if(value.endpoint&&value.userPoolId&&value.identityPoolId&&value.userPoolClientId)cloudConfig=value;}}catch{/* Cloud optional until deployment. */}try{await connectLocal();}catch{try{await loadDemo();}catch(error){notice(error.message,true);}}}
init();
