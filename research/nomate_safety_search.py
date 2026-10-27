"""Lazy safety-game search with backtracking of losing defender choices.

No oracle reports are proof leaves. Finite mate terminals propagate through
OR(Black)/AND(White); failed White choices are replaced. A closed reachable
nonwinning strategy is independently checked as a NoMate certificate.
This version requires no attacker king, so cycles cannot be White perpetual
checks. Budget exhaustion is UNKNOWN and retains the complete working graph.
"""
import argparse,json,time
from collections import deque
from pathlib import Path
import cshogi as cs,shogi
from memoryless_nomate_graph import key,checks,verify
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--seconds',type=float,default=30);ap.add_argument('--nodes',type=int,default=100000);ap.add_argument('--policy',choices=['capture','sparse','far','oracle'],default='capture');ap.add_argument('--rerank',action='store_true');ap.add_argument('--safe-strategy',type=Path);ap.add_argument('--oracle-ms',type=int,default=10);ap.add_argument('--oracle-limit',type=int,default=800);args=ap.parse_args()
initial=json.loads(args.source.read_text())['initial'];assert shogi.Board(initial).king_squares[0] is None
root=key(cs.Board(initial));nodes={};winning=set();todo=deque([root]);parents={};started=time.monotonic();status='UNKNOWN';proof=None
safe_hints={}
oracle=None;oracle_cache={};oracle_calls=0
if args.policy=='oracle':
    from synthesize import Engine
    oracle=Engine()
if args.safe_strategy:
    hint=json.loads(args.safe_strategy.read_text());assert hint['initial']==initial
    safe_hints=hint.get('safe_strategy',hint.get('nodes',{}))
if args.output.exists():
    old=json.loads(args.output.read_text());assert old['initial']==initial
    assert old.get('policy','capture')==args.policy or args.rerank
    if old['status']=='independently_certified_nomate':
        if oracle is not None:oracle.close()
        print('Already certified; no repeated search');raise SystemExit
    nodes=old['work_nodes'];winning=set(old['winning_states']);todo=deque(old['todo'])
    for state,row in nodes.items():
        edges=row.get('attacks',{}) if row['turn']==0 else dict(row.get('replies',[]))
        for child in edges.values():parents.setdefault(child,set()).add(state)
def queue_state(state):
    if state not in nodes and state not in winning:todo.append(state)
def white_choice(state):
    row=nodes[state]
    if state in safe_hints and 'reply' in safe_hints[state]:
        token=safe_hints[state]['reply'];child=safe_hints[state]['next']
        assert any(u==token and c==child for u,c in row['replies'])
        assert child not in winning
        row['choice']=[token,child];queue_state(child);return
    for u,child in row['replies']:
        if child not in winning:row['choice']=[u,child];queue_state(child);return
    row.pop('choice',None)
def reply_priority(state,u,b=None):
    global oracle_calls
    b=b or cs.Board(state+' 1');king=b.king_square(1)
    target=(int(u[2])-1)*9+ord(u[3])-97
    drop='*' in u;capture=not drop and bool(b.piece(target))
    from_sq=None if drop else (int(u[0])-1)*9+ord(u[1])-97
    isking=not drop and b.piece(from_sq)==cs.WKING
    distance=abs(target//9-king//9)+abs(target%9-king%9)
    if args.policy=='far':
        return (drop,not isking,-distance,not capture,u)
    if args.policy=='oracle':
        tag=(state,u)
        if tag not in oracle_cache and not drop and oracle_calls<args.oracle_limit:
            b.push_usi(u)
            try:pv,lines=oracle.solve(b.sfen(),args.oracle_ms)
            finally:b.pop()
            oracle_calls+=1
            oracle_cache[tag]=0 if lines[-1]=='checkmate nomate' else 2 if pv else 1
        return (drop,oracle_cache.get(tag,1),not isking,not capture,-distance,u)
    check_count=0
    if args.policy=='sparse' and not drop:
        b.push_usi(u);check_count=len(checks(b));b.pop()
    return (drop,check_count,not capture,not isking,{'P':0,'L':1,'N':2,'S':3,'G':4,'B':5,'R':6}.get(u[0],0) if drop else 0,distance,u)
def propagate(state):
    updates=deque([state])
    while updates:
        child=updates.popleft()
        if child in winning:continue
        winning.add(child)
        for parent in parents.get(child,()):
            if parent in winning:continue
            row=nodes[parent]
            if row['turn']==0:updates.append(parent)
            elif all(n in winning for _,n in row['replies']):updates.append(parent)
            elif row.get('choice',[None,None])[1] in winning:white_choice(parent)
def reachable():
    pending=[root];seen=set();result={};frontier=[]
    while pending:
        state=pending.pop()
        if state in seen:continue
        seen.add(state)
        if state in winning:return None,[]
        if state not in nodes:frontier.append(state);continue
        row=nodes[state]
        if row['turn']==0:result[state]=dict(attacks=row['attacks']);pending.extend(row['attacks'].values())
        else:
            assert 'choice' in row;u,child=row['choice'];result[state]=dict(reply=u,next=child);pending.append(child)
    return result,frontier
if nodes:
    for state,row in nodes.items():
        if row['turn']==1 and state not in winning:
            probe=cs.Board(state+' 1');row['replies'].sort(key=lambda r:reply_priority(state,r[0],probe));white_choice(state)
    _,frontier=reachable();todo=deque(dict.fromkeys(frontier))
started=time.monotonic()
while time.monotonic()-started<args.seconds and len(nodes)<args.nodes:
    if root in winning:status='finite_mate_detected_unverified';break
    if not todo:
        proof,frontier=reachable()
        if not frontier:
            assert proof is not None;status='closed_candidate';break
        todo.extend(frontier)
    state=todo.popleft()
    if state in nodes or state in winning:continue
    b=cs.Board(state+' 1')
    if b.turn==0:
        attacks={}
        for u in checks(b):b.push_usi(u);attacks[u]=key(b);b.pop()
        nodes[state]=dict(turn=0,attacks=attacks)
        for child in attacks.values():parents.setdefault(child,set()).add(state);queue_state(child)
        if any(child in winning for child in attacks.values()):propagate(state)
    else:
        options=[]
        for m in list(b.legal_moves):
            u=cs.move_to_usi(m);capture=bool(b.piece(cs.move_to(m)));king=not cs.move_is_drop(m) and b.piece(cs.move_from(m))==cs.WKING
            b.push(m);child=key(b);b.pop();options.append((cs.move_is_drop(m),not capture,not king,u,child))
        replies=[(u,child) for _,_,_,u,child in options];replies.sort(key=lambda r:reply_priority(state,r[0],b));nodes[state]=dict(turn=1,replies=replies)
        for _,child in replies:parents.setdefault(child,set()).add(state)
        if not replies or all(child in winning for _,child in replies):propagate(state)
        else:white_choice(state)
    if len(nodes)%500==0 and root not in winning:
        candidate,frontier=reachable()
        if candidate is not None and not frontier:proof=candidate;status='closed_candidate';break
        todo=deque(dict.fromkeys(frontier))
    if len(nodes)%1000==0:print(json.dumps(dict(expanded=len(nodes),winning=len(winning),pending=len(todo))),flush=True)
if oracle is not None:oracle.close()
result=dict(initial=initial,status=status,oracle_calls=oracle_calls,work_nodes=nodes,winning_states=sorted(winning),todo=list(todo),policy=args.policy,seconds=time.monotonic()-started,record_goal_achieved=False)
if status=='closed_candidate':
    stats=verify(initial,proof);result.update(status='independently_certified_nomate',nodes=proof,verification=stats)
args.output.write_text(json.dumps(result,separators=(',',':'))+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['nodes','work_nodes','winning_states','todo']}),flush=True)
