"""Small component minimax, full dual verification; no engine oracle."""
import json,cshogi as cs,shogi
from pathlib import Path
from functools import lru_cache
src=json.loads(Path('research/pawn-lance-rail-step-module.json').read_text());initial=src['initial']
def key(b):return ' '.join(b.sfen().split()[:3])
def moves(b):
 out=[]
 for m in list(b.legal_moves):
  u=cs.move_to_usi(m);b.push(m)
  if b.turn==cs.BLACK or b.is_check():out.append((u,key(b)))
  b.pop()
 return out
@lru_cache(None)
def solve(state,d):
 b=cs.Board(state+' 1');options=moves(b)
 if b.turn==cs.WHITE and not options:return True,dict(state=state,depth=d,mate=True)
 if d==0:return False,dict(state=state,depth=0,horizon=True)
 results=[]
 for u,child in options:
  value,node=solve(child,d-1);results.append(dict(move=u,next=node))
  if (b.turn==cs.BLACK and value) or (b.turn==cs.WHITE and not value):return value,dict(state=state,depth=d,children=[results[-1]])
 return b.turn==cs.WHITE,dict(state=state,depth=d,children=results)
def verify(node,value):
 b=shogi.Board(node['state']+' 1');n=cs.Board(b.sfen());legal={m.usi() for m in b.legal_moves};assert legal=={cs.move_to_usi(m) for m in n.legal_moves}
 if node.get('mate'):assert value and b.turn==shogi.WHITE and b.is_check() and not legal;return 1
 if node.get('horizon'):assert not value and (b.turn==shogi.BLACK or legal);return 1
 expected=set()
 for m in list(b.legal_moves):
  attacker=b.turn==shogi.BLACK;b.push(m)
  if not attacker or b.is_check():expected.add(m.usi())
  b.pop()
 children=node['children'];actual={r['move'] for r in children}
 exhaustive=(b.turn==shogi.BLACK and not value) or (b.turn==shogi.WHITE and value)
 assert actual==expected if exhaustive else len(children)==1 and actual<=expected
 if b.turn==shogi.WHITE and not value:
  # Negative certificates use genuine king evasions, not artificial futile interpositions.
  assert all(b.piece_at(shogi.Move.from_usi(r['move']).from_square).piece_type==shogi.KING for r in children)
 count=1
 for r in children:
  b.push_usi(r['move']);assert key(b)==r['next']['state'];assert r['next']['depth']==node['depth']-1;b.pop();count+=verify(r['next'],value)
 return count
root=key(cs.Board(initial));rows=[]
for d in [9,11]:
 value,node=solve(root,d);visits=verify(node,value);rows.append(dict(depth=d,mate_within=value,verified_visits=visits,strategy=node));print(d,value,visits,flush=True)
assert not rows[0]['mate_within'] and rows[1]['mate_within']
import copy
mutated=copy.deepcopy(rows[0]['strategy']);mutated['children']=[]
try:
 verify(mutated,False)
except AssertionError:
 print('Incomplete attacker coverage correctly rejected',flush=True)
else:
 raise AssertionError('Negative proof accepted with missing checking attacks')
Path('research/pawn-lance-rail-exact11-proof.json').write_text(json.dumps(dict(initial=initial,results=rows,exact_mate_plies=11,independent_dual_verification=True,negative_white_replies_all_king_moves=True,composition_uniqueness_unproved=True),indent=2)+'\n')
