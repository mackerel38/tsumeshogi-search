"""Regression cases: pinned capturer, legal pawn advance, legal checking drop."""
import json,sys
from pathlib import Path
import shogi,cshogi as cs
from orthodox_legal import legal_moves,is_legal
def sets(b):
    before=b.sfen();py={m.usi() for m in legal_moves(b)};n=cs.Board(before)
    assert py=={cs.move_to_usi(m) for m in n.legal_moves};assert b.sfen()==before
    assert {m.usi() for m in b.generate_pseudo_legal_moves() if is_legal(b,m)}==py
    assert b.sfen()==before
    return py
def main(path):
    src=json.loads(path.read_text());initial=src['state']+' 1';b=shogi.Board(initial)
    assert 'P*1b' in {m.usi() for m in b.legal_moves}
    for square in shogi.SQUARES:
        if b.piece_at(square):assert not is_legal(b,shogi.Move(None,square,drop_piece_type=shogi.PAWN))
    assert 'P*1b' not in sets(b)
    b.push_usi('P*1b');assert b.is_check() and not sets(b)
    b=shogi.Board(initial);b.remove_piece_from_hand(shogi.PAWN,shogi.BLACK)
    b.set_piece_at(shogi.SQUARE_NAMES.index('1c'),shogi.Piece(shogi.PAWN,shogi.BLACK))
    assert '1c1b' in sets(b)
    b.push_usi('1c1b');assert b.is_check() and not sets(b)
    b=shogi.Board(initial);b.remove_piece_at(shogi.SQUARE_NAMES.index('3a'))
    b.add_piece_into_hand(shogi.KNIGHT,shogi.WHITE)
    assert 'P*1b' in sets(b)
    b.push_usi('P*1b');assert '1a2a' in sets(b)
    print(json.dumps(dict(pinned_capture_pawn_drop_mate_rejected=True,board_pawn_mate_allowed=True,checking_pawn_drop_with_escape_allowed=True,independent_native_sets_agree=True)))
if __name__=='__main__':main(Path(sys.argv[1]))
