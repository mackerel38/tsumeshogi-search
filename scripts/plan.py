"""Parse bounded declarative requests, never issue text as shell code."""
import json,os,re
from pathlib import Path
ALLOWED=['horse-8a','horse-7b','horse-6c','horse-5d','horse-1d','horse-4f','no-king-core','spatial-pawn37-38','spatial-lance68-67','spatial-silver62-promote','spatial-pawn26-demote']
def request(body):
    match=re.search(r'```json\s*(.*?)\s*```',body,re.S)
    value=json.loads(match.group(1) if match else body)
    assert isinstance(value,dict)
    assert set(value)<= {'candidates','seconds','nodes','resume_run'}
    names=value.get('candidates',['horse-5d'])
    assert isinstance(names,list) and 1<=len(names)<=6 and len(names)==len(set(names))
    assert all(n in ALLOWED for n in names)
    seconds=value.get('seconds',60);nodes=value.get('nodes',200000)
    assert type(seconds) is int and 1<=seconds<=600
    assert type(nodes) is int and 10<=nodes<=1000000
    resume=value.get('resume_run',0)
    assert type(resume) is int and resume>=0
    return dict(include=[dict(candidate=n,seconds=seconds,nodes=nodes,resume_run=resume) for n in names])
if __name__=='__main__':
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    body=event['issue']['body'] if 'issue' in event else event.get('inputs',{}).get('request','{}')
    result=request(body or '{}')
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('matrix='+json.dumps(result)+'\n')
