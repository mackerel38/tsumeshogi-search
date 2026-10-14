"""Generate independent orthodox tsume seeds; no existing diagram is used.

Requires python-shogi and an external KomoringHeights executable.
These searches produce seeds, not a proof of originality or a record claim.
"""
import argparse
import collections
import json
import os
import pathlib
import random
import subprocess
import time

import shogi

TOTAL = {shogi.PAWN: 18, shogi.LANCE: 4, shogi.KNIGHT: 4,
         shogi.SILVER: 4, shogi.GOLD: 4, shogi.BISHOP: 2, shogi.ROOK: 2}
BASE = {p: p for p in TOTAL}
BASE.update({shogi.PROM_PAWN: shogi.PAWN, shogi.PROM_LANCE: shogi.LANCE,
             shogi.PROM_KNIGHT: shogi.KNIGHT, shogi.PROM_SILVER: shogi.SILVER,
             shogi.PROM_BISHOP: shogi.BISHOP, shogi.PROM_ROOK: shogi.ROOK})


class Engine:
    """Mate search with the side to move explicitly designated as attacker.

    This includes reverse-check positions with both kings present. Callers
    must pass an attacker-to-move checkpoint, rather than a defender node.
    """
    def __init__(self, executable=None):
        local = pathlib.Path(__file__).resolve().parents[1] / 'vendor/KomoringHeights/source/KomoringHeights-by-gcc'
        extended = local.parent.parent / 'source-depth8000/KomoringHeights-by-gcc'
        if extended.exists():
            local = extended
        if executable is None:
            executable = os.environ.get('TSUMESHOGI_ENGINE', str(local))
        elif executable == '/tmp/tsumeshogi-komoring/source/KomoringHeights-by-gcc':
            # Existing research scripts used this temporary build location.
            executable = str(local)
        self.executable = executable
        self.proc = subprocess.Popen([executable], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, text=True, bufsize=1)
        self.send('usi')
        self.until('usiok')
        for name, value in [('Threads', '1'), ('USI_Hash', '64'),
                            ('GenerateAllLegalMoves', 'true'),
                            ('RootIsAndNodeIfChecked', 'false'),
                            ('PostSearchLevel', 'MinLength')]:
            self.send(f'setoption name {name} value {value}')
        self.send('isready')
        self.until('readyok')

    def send(self, command):
        self.proc.stdin.write(command + '\n')
        self.proc.stdin.flush()

    def until(self, prefix):
        lines = []
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError('Engine exited')
            lines.append(line.strip())
            if line.startswith(prefix):
                return lines

    def solve(self, sfen, milliseconds):
        self.send('usinewgame')
        self.send('position sfen ' + sfen)
        self.send(f'go mate {milliseconds}')
        lines = self.until('checkmate ')
        result = lines[-1].split()[1:]
        if not result or result[0] in ('timeout', 'nomate', 'notimplemented'):
            return None, lines
        return result, lines

    def close(self):
        self.send('quit')
        self.proc.wait(timeout=5)


def prepare(board):
    """Assign every unused non-king piece to the defender."""
    used = collections.Counter()
    pawns = collections.Counter()
    for square in shogi.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.piece_type == shogi.KING:
            continue
        used[BASE[piece.piece_type]] += 1
        rank = square // 9
        if piece.piece_type == shogi.PAWN:
            pawns[piece.color, square % 9] += 1
        if piece.piece_type in (shogi.PAWN, shogi.LANCE):
            if rank == (0 if piece.color == shogi.BLACK else 8):
                return False
        if piece.piece_type == shogi.KNIGHT:
            if rank < 2 and piece.color == shogi.BLACK:
                return False
            if rank > 6 and piece.color == shogi.WHITE:
                return False
    if any(n > 1 for n in pawns.values()):
        return False
    for color in (shogi.BLACK, shogi.WHITE):
        for kind, n in board.pieces_in_hand[color].items():
            used[kind] += n
    if any(used[kind] > n for kind, n in TOTAL.items()):
        return False
    for kind, n in TOTAL.items():
        if n > used[kind]:
            board.add_piece_into_hand(kind, shogi.WHITE, n - used[kind])
    board.turn = shogi.BLACK
    king = board.king_squares[shogi.WHITE]
    return king is not None and not board.is_attacked_by(shogi.BLACK, king)


def fresh(rng):
    board = shogi.Board()
    board.clear()
    board.set_piece_at(rng.randrange(1, 8) + 9 * rng.randrange(3),
                       shogi.Piece(shogi.KING, shogi.WHITE))
    squares = list(range(54))
    rng.shuffle(squares)
    choices = [shogi.PAWN, shogi.PROM_PAWN, shogi.LANCE, shogi.KNIGHT,
               shogi.SILVER, shogi.GOLD, shogi.BISHOP, shogi.ROOK,
               shogi.PROM_BISHOP, shogi.PROM_ROOK]
    for color, count in [(shogi.BLACK, rng.randrange(4, 9)),
                         (shogi.WHITE, rng.randrange(2, 6))]:
        for _ in range(count):
            square = squares.pop()
            if board.piece_at(square) is None:
                board.set_piece_at(square, shogi.Piece(rng.choice(choices), color))
    if rng.random() < .6:
        board.add_piece_into_hand(rng.choice([shogi.GOLD, shogi.SILVER,
                                             shogi.KNIGHT, shogi.LANCE]), shogi.BLACK)
    return board


def mutate(sfen, rng):
    board = shogi.Board(sfen)
    board.pieces_in_hand[shogi.WHITE].clear()
    occupied = [s for s in shogi.SQUARES if board.piece_at(s)]
    source = rng.choice(occupied)
    piece = board.piece_at(source)
    dests = [s for s in range(63) if board.piece_at(s) is None]
    if not dests:
        return board
    dest = rng.choice(dests)
    if rng.random() < .75:
        near = [s for s in dests if abs(s // 9 - source // 9) <= 1
                and abs(s % 9 - source % 9) <= 1]
        if near:
            dest = rng.choice(near)
    board.remove_piece_at(source)
    board.set_piece_at(dest, piece)
    return board


def verify_line(sfen, moves):
    board = shogi.Board(sfen)
    for index, token in enumerate(moves):
        move = shogi.Move.from_usi(token)
        if not board.is_legal(move):
            raise ValueError(f'Illegal move {index + 1}: {token}')
        board.push(move)
        if index % 2 == 0 and not board.is_check():
            raise ValueError(f'Non-checking attack {index + 1}: {token}')
    if not board.is_checkmate():
        raise ValueError('Line does not end in checkmate')
    return dict(final_sfen=board.sfen(), attack_hand_empty=not board.pieces_in_hand[shogi.BLACK])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', required=True)
    parser.add_argument('--seconds', type=float, default=120)
    parser.add_argument('--seed', type=int, default=20261001)
    parser.add_argument('--output', default='research/search-results.json')
    args = parser.parse_args()
    rng = random.Random(args.seed)
    engine = Engine(args.engine)
    start = time.monotonic()
    pool, best, seen = [], None, set()
    counts = collections.Counter()
    try:
        while time.monotonic() - start < args.seconds:
            board = mutate(rng.choice(pool)['sfen'], rng) if pool and rng.random() < .8 else fresh(rng)
            if not prepare(board):
                counts['invalid'] += 1
                continue
            sfen = board.sfen()
            if sfen in seen:
                continue
            seen.add(sfen)
            pv, log = engine.solve(sfen, 80)
            counts['searched'] += 1
            if not pv:
                counts[log[-1]] += 1
                continue
            checked = verify_line(sfen, pv)
            record = dict(sfen=sfen, length=len(pv), pv=pv, line_check=checked, engine_log=log)
            counts['mates'] += 1
            pool.append(record)
            pool.sort(key=lambda x: x['length'], reverse=True)
            pool = pool[:30]
            if best is None or len(pv) > best['length']:
                best = record
                print(json.dumps(dict(best=best['length'], sfen=sfen, searched=counts['searched'])), flush=True)
                pathlib.Path(args.output).write_text(json.dumps(dict(seed=args.seed, counts=counts, best=best), ensure_ascii=False, indent=2)+'\n')
    finally:
        engine.close()
    result = dict(seed=args.seed, elapsed_seconds=time.monotonic()-start,
                  counts=counts, best=best, top_candidates=pool,
                  limitation='Search seeds only. No uniqueness, independent shortest-mate proof, or prior-art check.')
    pathlib.Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(counts=counts, best=None if best is None else best['length'])), flush=True)


if __name__ == '__main__':
    main()
