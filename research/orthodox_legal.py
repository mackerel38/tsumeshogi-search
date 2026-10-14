"""Python move generation with a pin-aware pawn-drop-mate test.

python-shogi 1.1.1's shortcut treats a pinned pawn capturer as an evasion.
We instead enumerate actual board evasions after a checking pawn drop.
No drop can evade an adjacent pawn check, so this test needs no recursion.
"""
import shogi
NO_DROPS=dict(pawns_drop=False,lances_drop=False,knights_drop=False,
              silvers_drop=False,golds_drop=False,bishops_drop=False,rooks_drop=False)

def king_safe(board,color):
    king=board.king_squares[color]
    return king is None or not board.is_attacked_by(color^1,king)

def has_board_evasion(board):
    color=board.turn
    for move in list(board.generate_pseudo_legal_moves(**NO_DROPS)):
        target=board.piece_at(move.to_square)
        if target and target.piece_type==shogi.KING:continue
        board.push(move);safe=king_safe(board,color);board.pop()
        if safe:return True
    return False

def legal_moves(board):
    color=board.turn
    for move in list(board.generate_pseudo_legal_moves()):
        target=board.piece_at(move.to_square)
        if target and target.piece_type==shogi.KING:continue
        board.push(move)
        safe=king_safe(board,color)
        if safe and move.drop_piece_type==shogi.PAWN:
            pawn_target=move.to_square+(-9 if color==shogi.BLACK else 9)
            if pawn_target==board.king_squares[color^1] and not has_board_evasion(board):safe=False
        board.pop()
        if safe:yield move
