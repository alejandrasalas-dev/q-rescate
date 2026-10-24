"""Windows integration evidence; run as a file so spawn imports a safe main."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    import argparse,json,time
    from dataclasses import asdict
    from qrescate_desktop.local_backend import LocalBackend,from_example
    from qrescate_desktop.models import Point,Zone
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=['classic','qaoa','exclusion','wide','cancel'],default='classic');parser.add_argument('--output',required=True);args=parser.parse_args()
    backend=LocalBackend();s=from_example();s.config.methods=['exact','greedy'];s.config.timeout_seconds=180
    if args.case=='qaoa':s.config.methods=['exact','greedy','qaoa'];s.destinations=s.destinations[:2]
    if args.case=='exclusion':
        d=s.destinations[0];s.zones.append(Zone('exclude-a','Destino A bloqueado',d.lat,d.lng,150,'exclusion'))
    if args.case=='wide':
        s.zones=[];s.destinations[1]=Point('B','Pangoa · amplio',-11.43,-74.49)
        s.config.timeout_seconds=240
    begin=time.monotonic();stages=[];job=backend.submit(s)
    if args.case=='cancel':backend.cancel(job)
    while True:
        snapshot=backend.status(job)
        text=' · '.join(snapshot.messages)
        if not stages or text!=stages[-1]:stages.append(text);print(text,flush=True)
        if snapshot.state in ('completed','cancelled','error'):break
        time.sleep(.2)
    payload={'case':args.case,'scenario':s.to_dict(),'snapshot':asdict(snapshot),'wall_seconds':time.monotonic()-begin,'stages':stages}
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    backend.shutdown();print('Final:',snapshot.state,flush=True)

if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
