"""Verify both resource-gate exits and two exact-entry NoMate certificates."""
import json,sys
from pathlib import Path
import shogi,cshogi as cs
from verify_nomate import verify
from orthodox_legal import legal_moves

def legal_pair(b,n):
    assert b.sfen()==n.sfen()
    assert {m.usi() for m in legal_moves(b)}=={cs.move_to_usi(m) for m in n.legal_moves}

def main(folder):
    contract=json.loads((folder/'contract.json').read_text())
    b=shogi.Board(contract['initial']);n=cs.Board(b.sfen());legal_pair(b,n)
    assert not b.is_check() and b.pieces_in_hand[shogi.BLACK]=={shogi.GOLD:1}
    found={}
    for m in list(legal_moves(b)):
        u=m.usi();b.push(m);n.push_usi(u)
        if b.is_check() and not list(legal_moves(b)):
            legal_pair(b,n);assert n.is_check() and not b.pieces_in_hand[shogi.BLACK]
            found[u]=b.sfen()
        b.pop();n.pop()
    assert found=={r['move']:r['final'] for r in contract['exit_moves']}
    results=[]
    for name in contract['negative_certificates']:
        d=json.loads((folder/name).read_text());stats=verify(d['initial'],d['nodes'])
        expected=shogi.Board(contract['initial'])
        if name=='gold0-nomate.json':
            expected.remove_piece_from_hand(shogi.GOLD,shogi.BLACK)
            expected.add_piece_into_hand(shogi.GOLD,shogi.WHITE)
        else:
            source=shogi.SQUARE_NAMES.index('2c');target=shogi.SQUARE_NAMES.index('2d')
            piece=expected.piece_at(source);assert piece==shogi.Piece(shogi.PROM_BISHOP,shogi.BLACK)
            expected.remove_piece_at(source);expected.set_piece_at(target,piece)
        assert expected.sfen()==d['initial'], 'NoMate certificate has a different gate entry'
        for state,row in d['nodes'].items():
            if 'reply' not in row:continue
            p=shogi.Board(state+' 1');m=shogi.Move.from_usi(row['reply']);assert not m.drop_piece_type
            if name=='gold0-nomate.json':assert p.piece_at(m.from_square).piece_type==shogi.KING
            elif p.piece_at(m.from_square).piece_type!=shogi.KING:
                assert row['reply']=='2b2c'
                q=cs.Board(p.sfen())
                for token in [row['reply'],'3d2c','1b2c']:
                    legal_pair(p,q);assert token in {x.usi() for x in legal_moves(p)}
                    p.push_usi(token);q.push_usi(token)
                assert p.sfen()==q.sfen()
        results.append(dict(certificate=name,verification=stats))
    print(json.dumps(dict(mate1_exits=sorted(found),all_exits_hand_empty=True,negative_results=results,record_goal_achieved=False)))

if __name__=='__main__':main(Path(sys.argv[1]))
