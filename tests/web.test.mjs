import test from 'node:test';
import assert from 'node:assert/strict';
import {validateReplay,csvFromFrames,secondsLabel} from '../web/state.js';
const frame={schema_version:'1.0',run_id:'r1',timestamp:1000,source:'simulation',site:{bounds_m:[0,0,10,10]},counts:{inventoried:0},scanner:{id:'RPi01',position:null},devices:[]};
test('reject mixed tasks and reversed replay time',()=>{
  assert.throws(()=>validateReplay({schema_version:'1.0',kind:'ble-inventory-replay',frames:[frame,{...frame,timestamp:999}]}));
  assert.throws(()=>validateReplay({schema_version:'1.0',kind:'ble-inventory-replay',frames:[frame,{...frame,run_id:'r2'}]}));
  assert.equal(validateReplay({schema_version:'1.0',kind:'ble-inventory-replay',frames:[frame]}).frames.length,1);
});
test('CSV neutralizes imported formula fields',()=>{
  const csv=csvFromFrames([{...frame,run_id:'=HYPERLINK("x")'}]);
  assert.ok(csv.includes("'=HYPERLINK"));
  assert.equal(secondsLabel(125),'02:05');
});
