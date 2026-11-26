// Local site configuration only; public/cloud/replay views cannot write settings.
export function initSiteSettings(context, onState, notify) {
  const button=document.getElementById('settings-button');
  const dialog=document.createElement('dialog');dialog.id='settings-dialog';
  dialog.innerHTML=`<form id="site-form"><h2>場地與 Anchor 座標</h2><p>座標保存在 RPi，不必重新燒錄 XIAO。保存會開始新巡查，舊紀錄保留。</p><div id="site-fields"></div><h3>Anchor</h3><p>Local 的 z 為場地相對高度；WGS84 高度為橢球高。Target 平面位置由定位計算。</p><div id="anchor-fields"></div><h3>Target 天線高度</h3><div id="target-fields"></div><pre id="site-preview" aria-live="polite"></pre><p id="site-error" role="alert"></p><div class="dialog-actions"><button type="button" class="button secondary" id="site-cancel">取消</button><button type="button" class="button secondary" id="site-reload">重新載入</button><button type="button" class="button secondary" id="site-check">計算預覽</button><button type="submit" class="button primary" id="site-save" disabled>保存並開始新巡查</button></div></form>`;
  document.body.append(dialog);
  const $=id=>dialog.querySelector(`#${id}`),form=$('site-form');
  let revision,original,rows=[],targetRows=[],checked=false,busy=false;
  function field(parent,label,value,type='number'){
    const wrap=document.createElement('label');wrap.textContent=label;
    const input=document.createElement('input');input.type=type;input.value=value??'';input.required=true;
    if(type==='number')input.step='any';wrap.append(input);parent.append(wrap);return input;
  }
  function select(parent,label,options,value){
    const wrap=document.createElement('label');wrap.textContent=label;const input=document.createElement('select');
    for(const [v,name] of options){const o=document.createElement('option');o.value=v;o.textContent=name;input.append(o);}input.value=value;wrap.append(input);parent.append(wrap);return input;
  }
  let frame,bounds,scanner,status,geoEnabled,geoFields,geoPanel,geoSource;
  function render(settings){
    original=settings;rows=[];targetRows=[];checked=false;$('site-save').disabled=true;$('site-preview').textContent='';
    const box=$('site-fields');box.replaceChildren();box.className='site-grid';
    frame=field(box,'場地座標系 ID',settings.frame_id,'text');
    scanner=field(box,'RPi 天線高度（m）',settings.scanner_height_m);
    status=select(box,'座標量測狀態',[['example','示例／尚未量測'],['measured','已完成場地量測']],settings.configuration_status);
    bounds=['X 最小（m）','Y 最小（m）','X 最大（m）','Y 最大（m）'].map((name,i)=>field(box,name,settings.bounds_m[i]));
    geoEnabled=select(box,'地理對準',[['no','尚無 WGS84 原點'],['yes','啟用 WGS84 原點']],settings.georeference?'yes':'no');
    geoPanel=document.createElement('div');geoPanel.className='site-grid';box.append(geoPanel);
    const g=settings.georeference??{};
    geoFields=Object.fromEntries([['latitude_deg','原點緯度（度）'],['longitude_deg','原點經度（度）'],['height_m','原點橢球高（m）'],['rotation_deg','Local X 自東向逆時針角（度）'],['transform_id','轉換版本 ID']].map(([key,label])=>[key,field(geoPanel,label,g[key]??(key==='transform_id'?'site-v1':0),key==='transform_id'?'text':'number')]));
    const sources=[['example','示例／尚未實測'],['measured','已完成地理對準量測']];
    if(g.source&&!sources.some(([value])=>value===g.source))sources.push([g.source,`原有來源：${g.source}`]);
    geoSource=select(geoPanel,'地理原點來源',sources,g.source??'example');
    const setGeo=()=>{geoPanel.hidden=geoEnabled.value!=='yes';for(const input of [...Object.values(geoFields),geoSource])input.disabled=geoPanel.hidden;};setGeo();geoEnabled.addEventListener('change',setGeo);
    const anchors=$('anchor-fields');anchors.replaceChildren();
    for(const a of settings.anchors){
      const row=document.createElement('fieldset');const title=document.createElement('legend');title.textContent=a.id;row.append(title);anchors.append(row);
      const mode=select(row,'輸入座標',[['local','Local（m）'],['wgs','WGS84（度／m）']],a.position_wgs84?'wgs':'local');
      const local=document.createElement('div');local.className='site-grid';row.append(local);
      const xyz=['X（m）','Y（m）','Z 相對高度（m）'].map((name,i)=>field(local,name,a.position[i]));
      const geographic=document.createElement('div');geographic.className='site-grid';row.append(geographic);
      const g=a.position_wgs84??a.computed_wgs84??{};
      const llh=['latitude_deg','longitude_deg','height_m'].map((key,i)=>field(geographic,['緯度（度）','經度（度）','橢球高（m）'][i],g[key]??''));
      const setMode=()=>{local.hidden=mode.value!=='local';geographic.hidden=mode.value!=='wgs';xyz.forEach(i=>i.disabled=local.hidden);llh.forEach(i=>i.disabled=geographic.hidden);};setMode();mode.addEventListener('change',setMode);rows.push({id:a.id,mode,xyz,llh});
    }
    const targets=$('target-fields');targets.replaceChildren();targets.className='site-grid';
    for(const t of settings.targets)targetRows.push({id:t.id,input:field(targets,`${t.id} 高度（m）`,t.height_m)});
  }
  function collect(){
    if(!form.reportValidity())throw new Error('請填入完整且有效的欄位');
    const n=input=>{if(input.value.trim()==='')throw new Error('座標不可空白');const v=Number(input.value);if(!Number.isFinite(v))throw new Error('請輸入有限數值');return v;};
    return {frame_id:frame.value.trim(),bounds_m:bounds.map(n),scanner_height_m:n(scanner),configuration_status:status.value,
      georeference:geoEnabled.value==='yes'?{...Object.fromEntries(Object.entries(geoFields).map(([k,v])=>[k,k==='transform_id'?v.value.trim():n(v)])),source:geoSource.value}:null,
      anchors:rows.map(r=>r.mode.value==='local'?{id:r.id,position:r.xyz.map(n)}:{id:r.id,position_wgs84:Object.fromEntries(['latitude_deg','longitude_deg','height_m'].map((k,i)=>[k,n(r.llh[i])]))}),
      targets:targetRows.map(t=>({id:t.id,height_m:n(t.input)}))};
  }
  async function request(path,body){
    const {mode,bootstrap}=context();if(mode!=='local'||!bootstrap?.settings_editable)throw new Error('請使用 RPi 本地即時頁面編輯');
    const r=await fetch(`./api/settings${path}`,{method:body?'POST':'GET',cache:'no-store',headers:{'Content-Type':'application/json','X-Control-Token':bootstrap.control_token},...(body?{body:JSON.stringify(body)}:{})});
    if(!r.ok)throw new Error(r.status===409?'設定版本已變更。請先另行記錄你的修改，再按重新載入。':await r.text());return r.json();
  }
  async function run(action){if(busy)return;busy=true;$('site-error').textContent='';for(const id of ['site-check','site-save','site-reload'])$(id).disabled=true;
    try{await action();}catch(error){$('site-error').textContent=error.message;$('site-preview').textContent='';checked=false;}finally{busy=false;$('site-check').disabled=false;$('site-reload').disabled=false;$('site-save').disabled=!checked;}}
  async function load(){const data=await request('');revision=data.revision;render(data.settings);}
  button.onclick=()=>run(async()=>{await load();dialog.showModal();});
  $('site-reload').onclick=()=>run(load);$('site-cancel').onclick=()=>dialog.close();
  function invalidate(){checked=false;$('site-save').disabled=true;$('site-preview').textContent='';}
  form.addEventListener('input',invalidate);
  form.addEventListener('change',invalidate);
  $('site-check').onclick=()=>run(async()=>{const data=await request('/preview',{settings:collect()});
    $('site-preview').textContent=[...data.settings.anchors.map(a=>`${a.id} Local: ${a.position.map(v=>v.toFixed(3)).join(', ')} m${a.computed_wgs84?` · WGS84: ${a.computed_wgs84.latitude_deg.toFixed(7)}, ${a.computed_wgs84.longitude_deg.toFixed(7)}`:''}`),...data.warnings].join('\n');checked=true;});
  form.onsubmit=e=>{e.preventDefault();if(!checked||busy)return;run(async()=>{const data=await request('',{expected_revision:revision,settings:collect()});onState(data.state);dialog.close();notify('場地設定已保存，已開始新巡查；舊紀錄保留。');});};
  return {updateAvailability(){const {mode,bootstrap}=context();button.disabled=mode!=='local'||!bootstrap?.settings_editable;button.title=button.disabled?'請在 RPi 本地即時模式設定座標':'';}};
}
