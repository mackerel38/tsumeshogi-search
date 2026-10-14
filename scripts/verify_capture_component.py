"""Independently verify finite positive/negative component certificates."""
import json,sys
from pathlib import Path
from collections import Counter
import shogi,cshogi as cs
from orthodox_legal import legal_moves
def state(b):return ' '.join(b.sfen().split()[:3])
def pair(sfen):
    b=shogi.Board(sfen);n=cs.Board(sfen)
    assert {m.usi() for m in legal_moves(b)}=={cs.move_to_usi(m) for m in n.legal_moves}
    return b,n
def push(b,n,u):
    assert u in {m.usi() for m in legal_moves(b)}
    assert u in {cs.move_to_usi(m) for m in n.legal_moves}
    b.push_usi(u);n.push_usi(u);assert b.sfen()==n.sfen()
def main(folder):
    positive=json.loads((folder/'upper-proof.json').read_text());negative=json.loads((folder/'lower-proof.json').read_text())
    assert positive['initial']==negative['initial']==(folder/'input.sfen').read_text().strip()
    witnesses={}
    for r in json.loads((folder/'lower-drop-witnesses.json').read_text()):
        tokens=r.get('moves') or [r['drop'],r['checking_capture'],r['king_recapture']]
        b,n=pair(r['state']+' 1')
        for u in tokens:push(b,n,u)
        assert b.sfen()==r['after']
        witnesses[(r['state'],tokens[0])]=tokens
    leaves=[]
    def positive_walk(node,remaining,history):
        assert remaining>=0
        b,n=pair(node['sfen']);k=state(b);history=history.copy();history[k]+=1;assert history[k]<4
        if node.get('mate'):
            assert b.turn==shogi.WHITE and b.is_check() and n.is_check() and not list(legal_moves(b)) and not list(n.legal_moves)
            empty=not b.pieces_in_hand[0];assert empty==node['black_hand_empty'];leaves.append(empty);return
        assert remaining>0
        if b.turn==shogi.BLACK:
            push(b,n,node['move']);assert b.is_check() and b.sfen()==node['next']['sfen']
            positive_walk(node['next'],remaining-1,history)
        else:
            legal={m.usi() for m in legal_moves(b)};assert legal=={r['move'] for r in node['defenses']} and len(legal)==len(node['defenses'])
            for r in node['defenses']:
                q,t=pair(node['sfen']);push(q,t,r['move']);assert q.sfen()==r['next']['sfen']
                positive_walk(r['next'],remaining-1,history)
    assert positive['strategy']['sfen']==positive['initial']
    positive_walk(positive['strategy'],positive['upper_bound'],Counter())
    nodes=negative['strategy_dag']['nodes'];seen=set()
    def lower_walk(i):
        if i in seen:return
        row=nodes[i];b,n=pair(row['state']+' 1');depth=row['depth']
        if row.get('horizon'):
            assert depth==0 and (b.turn==shogi.BLACK or list(legal_moves(b)));seen.add(i);return
        children=row['children'];actual={r['move'] for r in children}
        if b.turn==shogi.BLACK:
            wanted=set()
            for m in list(legal_moves(b)):
                b.push(m)
                if b.is_check():wanted.add(m.usi())
                b.pop()
            assert wanted==actual and len(actual)==len(children)
        else:
            assert b.is_check() and len(children)==1
            u=children[0]['move'];m=shogi.Move.from_usi(u)
            if m.drop_piece_type:assert (row['state'],u) in witnesses
        for r in children:
            q,t=pair(row['state']+' 1');push(q,t,r['move']);child=nodes[r['next']]
            assert state(q)==child['state'] and child['depth']==depth-1
            if b.turn==shogi.BLACK:assert q.is_check()
            lower_walk(r['next'])
        seen.add(i)
    root=negative['strategy_dag']['root'];assert nodes[root]['state']==state(shogi.Board(positive['initial'])) and nodes[root]['depth']==negative['depth']
    assert negative['depth']==positive['upper_bound']-2
    lower_walk(root)
    print(json.dumps(dict(shortest_plies=positive['upper_bound'],mating_leaves=len(leaves),hand_empty_leaves=sum(leaves),lower_nodes=len(seen),effective_drop_witnesses=len(witnesses),composition_uniqueness_unproved=True,record_goal_achieved=False)))
if __name__=='__main__':main(Path(sys.argv[1]))
