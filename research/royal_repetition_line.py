"""Validate checking lines with full-state occurrence counts, including start.

This validates a particular line, not forced play or shortest mate. Fourfold
repetition is reported at the first offending ply, even if the line later
changes course and ends in mate. All earlier positions must be counted.
"""
from collections import Counter

import cshogi
import shogi


def validate(initial, moves):
    board = shogi.Board(initial)
    native = cshogi.Board(initial)
    state = lambda b: ' '.join(b.sfen().split()[:3])
    occurrences = Counter({state(board): 1})
    returns = []
    for ply, token in enumerate(moves, 1):
        move = shogi.Move.from_usi(token)
        # python-shogi's is_legal can accept a drop on an occupied square;
        # use its complete legal generator, as we do for the native library.
        if token not in {m.usi() for m in board.legal_moves}:
            return dict(valid=False, reason='illegal move', ply=ply, move=token)
        if token not in [cshogi.move_to_usi(m) for m in native.legal_moves]:
            return dict(valid=False, reason='legality disagreement between libraries',
                        ply=ply, move=token, state=board.sfen())
        attacker_moved = board.turn == shogi.BLACK
        board.push(move)
        native.push_usi(token)
        assert board.sfen() == native.sfen()
        if attacker_moved and not board.is_check():
            return dict(valid=False, reason='nonchecking attack', ply=ply, move=token)
        current = state(board)
        occurrences[current] += 1
        if occurrences[current] > 1:
            returns.append(dict(ply=ply, occurrence=occurrences[current], state=current))
        if occurrences[current] == 4:
            return dict(valid=False, reason='fourfold repetition during continuous attack checks',
                        ply=ply, move=token, state=current, returns=returns)
    return dict(valid=True, plies=len(moves), final=board.sfen(),
                mate=board.turn == shogi.WHITE and board.is_checkmate(),
                maximum_occurrences=max(occurrences.values()), returns=returns)


def main():
    import json
    from pathlib import Path
    source = json.loads(Path('research/royal-edge22-rook82-horse54-screens.json').read_text())
    pulse = source['pulse']
    exit_line = source['rows'][0]['pv']
    from reversecheck_flag_entry import verify
    proof = json.loads(Path('research/royal-edge22-rook82-horse54-shortcut-proof.json').read_text())
    leaves = verify(proof['strategy'], proof['upper_bound'])
    rows = []
    for cycles in range(4):
        moves = pulse * cycles + exit_line
        result = validate(source['initial'], moves)
        assert result['valid'] == (cycles < 3)
        if cycles < 3:
            assert result['mate'] and result['plies'] == 4 * cycles + 5
        else:
            assert result['ply'] == 12
        rows.append(dict(cycles=cycles, moves=moves, validation=result))
    # Verify the full mating tail after two selected cooperative cycles.
    # Coverage of the tail does not make the selected prefix forced.
    board = shogi.Board(source['initial'])
    counts = Counter({' '.join(board.sfen().split()[:3]): 1})
    for token in pulse * 2:
        board.push_usi(token)
        counts[' '.join(board.sfen().split()[:3])] += 1
    assert ' '.join(board.sfen().split()[:3]) == ' '.join(proof['root'].split()[:3])
    def walk(node, history):
        assert history[' '.join(node['sfen'].split()[:3])] <= 3
        if node.get('mate'):
            return 1
        children = [node['next']] if 'move' in node else [r['next'] for r in node['defenses']]
        result = 0
        for child in children:
            following = history.copy()
            following[' '.join(child['sfen'].split()[:3])] += 1
            result += walk(child, following)
        return result
    tail_leaves = walk(proof['strategy'], counts)
    assert tail_leaves == len(leaves)
    out = dict(scope=__doc__, initial=source['initial'], pulse=pulse, rows=rows,
               early_exit_upper_bound=5, early_exit_proof='royal-edge22-rook82-horse54-shortcut-proof.json',
               full_tail_history_verified=True, tail_leaves=tail_leaves,
               forced_repetition_certified=False, record_goal_achieved=False)
    Path('research/royal-edge22-repetition-before-exit.json').write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps([dict(cycles=r['cycles'], valid=r['validation']['valid'],
                           plies=r['validation'].get('plies'), first_violation=r['validation'].get('ply')) for r in rows]))


if __name__ == '__main__':
    main()
