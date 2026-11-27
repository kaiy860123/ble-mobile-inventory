"""Read-only local API check. Snapshot sightings are not packet-rate or precision evidence."""
import argparse
import json
from pathlib import Path
import time
from urllib.request import urlopen
from urllib.error import URLError

EXPECTED={'A01','A02','A03','A04','T01','T02'}

def inspect_state(state, started_at):
    if not isinstance(state,dict):raise ValueError('API state must be an object')
    if state.get('source')!='physical' or state.get('input_mode')!='ble':
        raise ValueError('Requires physical source and ble input mode; synthetic/replay is not hardware evidence')
    if not state.get('active'):
        raise ValueError('Start a new active patrol in the local dashboard before checking')
    if state.get('input_error'):
        raise ValueError('BLE input reports an error; inspect the local service log')
    seen=set()
    for device in state.get('devices',[]):
        if not isinstance(device,dict):raise ValueError('Invalid device record')
        stamp=device.get('last_seen')
        if device.get('id') in EXPECTED and isinstance(stamp,(int,float)) and started_at<=stamp<=time.time()+2:
            seen.add(device['id'])
    return seen

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',required=True,help='Local RPi HTTP service URL')
    p.add_argument('--duration',type=int,default=60)
    p.add_argument('--output',type=Path,default=Path('artifacts/hardware/readiness.json'))
    args=p.parse_args()
    if not 1<=args.duration<=300:p.error('--duration must be 1..300 seconds')
    started=time.time();deadline=time.monotonic()+args.duration
    result={'scope':'physical API sightings only; no packet loss or precision claim','started_at':started,'expected_ids':sorted(EXPECTED),'seen_ids':[],'missing_ids':sorted(EXPECTED),'run_id':None,'samples':0,'passed':False,'error':None}
    seen=set()
    try:
        while time.monotonic()<deadline:
            with urlopen(args.url.rstrip('/')+'/api/state',timeout=5) as response:state=json.load(response)
            found=inspect_state(state,started)
            run_id=state.get('run_id')
            if not run_id:raise ValueError('Missing run_id')
            if result['run_id'] is not None and result['run_id']!=run_id:raise ValueError('Patrol changed during check; rerun for a single run_id')
            result['run_id']=run_id;seen|=found;result['samples']+=1
            result['seen_ids']=sorted(seen);result['missing_ids']=sorted(EXPECTED-seen)
            print('Received since check began: '+(', '.join(sorted(seen)) or '(none)'),flush=True)
            time.sleep(min(1,max(0,deadline-time.monotonic())))
        result['passed']=seen==EXPECTED
    except (OSError,URLError,ValueError,TypeError) as e:
        result['error']=str(e)
    finally:
        result['finished_at']=time.time();args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
