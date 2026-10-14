"""Run one exact restoration search and preserve its checkpoint and provenance."""
import argparse,json,os,shutil,subprocess,time
from pathlib import Path
from plan import ALLOWED
p=argparse.ArgumentParser();p.add_argument('--candidate',choices=ALLOWED,required=True);p.add_argument('--seconds',type=int,default=60);p.add_argument('--nodes',type=int,default=200000);p.add_argument('--output',type=Path,default=Path('/results'));p.add_argument('--resume',type=Path);args=p.parse_args()
assert 1<=args.seconds<=600 and 10<=args.nodes<=1000000
args.output.mkdir(parents=True,exist_ok=True)
tag=args.candidate;stem='royal-latent-return-'+tag
if args.resume:
    for suffix in ['.json','.json.gz']:
        matches=list(args.resume.rglob(stem+suffix))
        assert len(matches)<=1, 'Ambiguous checkpoint'
        if matches:shutil.copyfile(matches[0],Path('research')/(stem+suffix))
command=['python','research/royal_latent_return.py','--source',f'candidates/{tag}.json','--tag',tag,'--all-pieces','--seconds',str(args.seconds),'--nodes',str(args.nodes)]
if tag in ['horse-5d','no-king-core']:command+=['--goal-source',f'candidates/{tag}-completions.json','--completion-distance']
started=time.time();result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
(args.output/'log.txt').write_text(result.stdout)
for suffix in ['.json','.json.gz']:
    path=Path('research')/(stem+suffix)
    if path.exists():shutil.copyfile(path,args.output/path.name)
metadata=dict(candidate=tag,command=command,exit_code=result.returncode,elapsed_seconds=time.time()-started,commit=os.environ.get('SEARCH_COMMIT'),run_id=os.environ.get('SEARCH_RUN_ID'),proof_scope='Cooperative checking restoration only; NOT forced mate or tsume length',tsume_rules_fully_verified=False)
(args.output/'provenance.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(result.stdout);raise SystemExit(result.returncode)
