export const qualityLabels = {valid:'有效估計',fixed:'已知座標',insufficient:'資料不足',stale:'最後有效位置',unseen:'尚未偵測'};
export function finite(value) { return typeof value === 'number' && Number.isFinite(value); }
export function number(value, digits=2) { return finite(value) ? value.toFixed(digits) : '—'; }
export function validateReplay(value) {
  if (value?.schema_version !== '1.0' || value?.kind !== 'ble-inventory-replay' || !Array.isArray(value.frames) || !value.frames.length || value.frames.length > 20000) throw new Error('請匯入本專題匯出的有效回放 JSON（最多 20,000 影格）。');
  let previous = -Infinity;
  const runId = value.frames[0].run_id;
  for (const frame of value.frames) {
    if (frame.schema_version !== '1.0' || !finite(frame.timestamp) || frame.timestamp < previous || frame.run_id !== runId || !['physical','simulation'].includes(frame.source) || !Array.isArray(frame.devices) || frame.devices.length>256 || !frame.scanner || !frame.site || !frame.counts) throw new Error('回放包含無效欄位、混合任務或時間順序錯誤。');
    const bounds = frame.site.bounds_m;
    if (!Array.isArray(bounds) || bounds.length!==4 || !bounds.every(finite) || bounds[0]>=bounds[2] || bounds[1]>=bounds[3]) throw new Error('無效場地範圍。');
    for (const device of [frame.scanner,...frame.devices]) {
      if (typeof device.id !== 'string' || device.id.length>64 || (device.position && (!finite(device.position.x_m)||!finite(device.position.y_m)))) throw new Error('無效設備或位置。');
      const geo = device.position?.wgs84;
      if (geo && (!finite(geo.latitude_deg)||!finite(geo.longitude_deg)||Math.abs(geo.latitude_deg)>90||Math.abs(geo.longitude_deg)>180)) throw new Error('無效地理座標。');
    }
    previous=frame.timestamp;
  }
  return value;
}
export function allDevices(frame) {
  if (!frame) return [];
  return [{...frame.scanner,role:'scanner',last_seen:frame.last_observation_at,visible:frame.scanner.quality==='valid'},...frame.devices];
}
export function secondsLabel(seconds) {
  const value=Math.max(0,Math.floor(seconds));
  return `${Math.floor(value/60).toString().padStart(2,'0')}:${(value%60).toString().padStart(2,'0')}`;
}
export function csvFromFrames(frames) {
  const columns=['run_id','source','timestamp','device_id','role','visible','quality','last_seen','position_at','rssi_dbm','x_m','y_m','latitude_deg','longitude_deg','residual_m'];
  const escape=value=>{
    let s=String(value??'');
    // Prevent spreadsheet formula execution for imported, user-controlled text fields.
    if (/^[=+@\t\r]/.test(s) || (/^-/.test(s) && !/^-\d+(\.\d+)?$/.test(s))) s="'"+s;
    return `"${s.replaceAll('"','""')}"`;
  };
  const rows=[columns];
  for(const frame of frames) for(const d of allDevices(frame)){
    const p=d.position??{},g=p.wgs84??{};
    rows.push([frame.run_id,frame.source,frame.timestamp,d.id,d.role,d.visible,d.quality,d.last_seen,d.position_at,d.rssi_dbm,p.x_m,p.y_m,g.latitude_deg,g.longitude_deg,p.residual_m]);
  }
  return '\ufeff'+rows.map(row=>row.map(escape).join(',')).join('\r\n');
}
