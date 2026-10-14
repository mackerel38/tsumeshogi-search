"""Cooperative exact restoration search for the latent Lance recapture core.

Find the initial board and turn with the requested White pawn transfer to Black
(one by default).
An explicit --target-source instead specifies an exact normal-stock final SFEN,
for example the original frame with one White pawn advanced by one square.
By default only P/L/B/R/K may move; --all-pieces removes this restriction.
No assertion that excluded choices are refuted.
Complete checking lines are history-validated if a target is found.
Identical states are merged for connectivity only, not forced-mate length.
"""
import collections
import argparse
import gzip
import hashlib
import heapq
import json
import time
from pathlib import Path
import cshogi as cs
import shogi
from royal_repetition_line import validate


def key(b):
    return ' '.join(b.sfen().split()[:3])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path)
    ap.add_argument('--tag', default='')
    ap.add_argument('--prefix', nargs='+')
    ap.add_argument('--all-pieces', action='store_true')
    ap.add_argument('--nodes', type=int, default=120000)
    ap.add_argument('--seconds', type=float, default=40)
    ap.add_argument('--pawn-transfer', type=int, default=1)
    ap.add_argument('--target-source', type=Path,
                    help='Exact target SFEN in a JSON target field; replaces the default hand-pawn transfer target')
    ap.add_argument('--final-rook-return', action='store_true',
                    help='Search the validated R82->83, King23->24 predecessor of the final board')
    ap.add_argument('--seed-cache', type=Path,
                    help='Reuse transitions with the same root and move policy, possibly a different target')
    ap.add_argument('--goal-source', type=Path,
                    help='Exact predecessor SFEN and verified completion suffix for the restoration goal')
    ap.add_argument('--completion-distance', action='store_true',
                    help='Prioritize distance to any verified completion predecessor, not only the final diagram')
    args = ap.parse_args()
    assert args.nodes > 0 and args.seconds > 0 and args.pawn_transfer > 0
    default_allowed = {cs.PAWN, cs.LANCE, cs.BISHOP, cs.ROOK, cs.KING,
                       cs.PROM_PAWN, cs.PROM_LANCE, cs.PROM_BISHOP, cs.PROM_ROOK}
    allowed = default_allowed | ({cs.KNIGHT, cs.SILVER, cs.GOLD,
                                  cs.PROM_KNIGHT, cs.PROM_SILVER}
                                 if args.all_pieces else set())
    source = {} if args.source else json.loads(Path('research/royal-latent-recapture.json').read_text())
    if args.source:
        alternate = json.loads(args.source.read_text())
        source['initial'] = alternate['initial']
        source['delayed_line'] = alternate.get('delayed_line', ['2d2f', '2g1g'])
    if args.prefix:
        source['delayed_line'] = args.prefix
    if args.source or args.prefix:
        source['delayed_validation'] = validate(source['initial'], source['delayed_line'])
        assert source['delayed_validation']['valid']
    root = cs.Board(source['delayed_validation']['final'])
    target = shogi.Board(source['initial'])
    if args.target_source:
        exact_target = json.loads(args.target_source.read_text())
        target = shogi.Board(exact_target['target'])
        from synthesize import prepare
        target_sfen = target.sfen()
        assert target.turn == shogi.BLACK and prepare(target)
        assert key(target) == key(shogi.Board(target_sfen)), 'Exact target must already account for normal stock'
    else:
        for _ in range(args.pawn_transfer):
            target.remove_piece_from_hand(shogi.PAWN, shogi.WHITE)
            target.add_piece_into_hand(shogi.PAWN, shogi.BLACK)
    final_goal = key(target)
    suffix = []
    completion_goals = None
    if args.goal_source:
        assert not args.final_rook_return
        completion = json.loads(args.goal_source.read_text())
        if 'rows' in completion:
            completion_goals = {final_goal: []}
            for row in completion['rows']:
                predecessor = shogi.Board(row['predecessor'])
                completion_validation = validate(predecessor.sfen(), row['suffix'])
                assert completion_validation['valid']
                assert key(shogi.Board(completion_validation['final'])) == final_goal
                completion_goals.setdefault(key(predecessor), row['suffix'])
        else:
            target = shogi.Board(completion['predecessor'])
            suffix = completion['suffix']
            completion_validation = validate(target.sfen(), suffix)
            assert completion_validation['valid']
            assert key(shogi.Board(completion_validation['final'])) == final_goal
    if args.final_rook_return:
        for old, new in [('8c', '8b'), ('2d', '2c')]:
            old_square, new_square = (shogi.SQUARE_NAMES.index(s) for s in (old, new))
            piece = target.piece_at(old_square)
            assert piece is not None and target.piece_at(new_square) is None
            target.remove_piece_at(old_square)
            target.set_piece_at(new_square, piece)
        suffix = ['8b8c', '2c2d']
        suffix_validation = validate(target.sfen(), suffix)
        assert suffix_validation['valid'] and key(shogi.Board(suffix_validation['final'])) == final_goal
    goal = key(target)
    completion_goals = completion_goals or {goal: suffix}
    completion_hash = hashlib.sha256(json.dumps(completion_goals, sort_keys=True).encode()).hexdigest()
    baseline = cs.Board(target.sfen())
    score_targets = ([cs.Board(state + ' 1') for state in completion_goals]
                     if args.completion_distance else [baseline])
    base_pieces = baseline.pieces
    score_variants = []
    for candidate in score_targets:
        pieces = candidate.pieces
        score_variants.append(([(s, p) for s, p in enumerate(pieces)
                                if p != base_pieces[s]],
                               tuple(x for hand in candidate.pieces_in_hand for x in hand)))
    stem = 'research/royal-latent-return' + ('-'+args.tag if args.tag else '')
    cache = Path(stem+'.json.gz')
    nodes = {key(root): dict(sfen=root.sfen(), parent=None)}
    resumed = 0
    source_cache = cache if cache.exists() else args.seed_cache
    if source_cache:
        previous = json.loads(gzip.decompress(source_cache.read_bytes()))
        assert previous['root'] == key(root)
        if source_cache == cache:
            assert previous['target'] == goal
            if args.goal_source:
                previous_hash = previous.get('completion_goals_sha256')
                if previous_hash is None:
                    previous_hash = hashlib.sha256(json.dumps(
                        {previous['target']: previous.get('suffix', [])}, sort_keys=True).encode()).hexdigest()
                assert previous_hash == completion_hash
        assert previous.get('allowed_piece_types', sorted(default_allowed)) == sorted(allowed), 'Cannot reuse edges from a different move policy'
        if source_cache == cache and (previous['found'] or previous['complete']):
            print('Saved search terminal')
            return
        nodes = previous['nodes']
        resumed = len(nodes)
    def score(state):
        if state in completion_goals:
            return -1
        b = cs.Board(nodes[state]['sfen'])
        pieces = b.pieces
        difference = sum(x != y for x, y in zip(pieces, base_pieces))
        hands = tuple(x for hand in b.pieces_in_hand for x in hand)
        hand_scores = {}
        values = []
        for changes, wanted_hands in score_variants:
            if wanted_hands not in hand_scores:
                hand_scores[wanted_hands] = 4 * sum(abs(x-y) for x,y in zip(hands,wanted_hands))
            board_score = difference + sum((pieces[s] != p) - (pieces[s] != base_pieces[s])
                                           for s,p in changes)
            values.append(8 * board_score + hand_scores[wanted_hands])
        return min(values)
    queue = [(score(k),i,k) for i,(k,n) in enumerate(nodes.items()) if 'edges' not in n or k in completion_goals]
    heapq.heapify(queue)
    serial = len(nodes)
    started = time.monotonic()
    found = None
    cutoff = None
    expanded = 0
    frozen = {s for s in range(81) if baseline.piece(s) and baseline.piece_type(s) not in allowed}
    while queue:
        if len(nodes) >= resumed + args.nodes:
            cutoff = 'node budget'
            break
        if time.monotonic()-started >= args.seconds:
            cutoff = 'time budget'
            break
        _,_,state = heapq.heappop(queue)
        if state in completion_goals:
            found = state
            suffix = completion_goals[state]
            break
        node = nodes[state]
        b = cs.Board(node['sfen'])
        edges = []
        for move in list(b.legal_moves):
            if cs.move_to(move) in frozen:
                continue
            token = cs.move_to_usi(move)
            if cs.move_is_drop(move):
                if token[0] not in ('PLNSGBR' if args.all_pieces else 'PLBR'):
                    continue
            elif b.piece_type(cs.move_from(move)) not in allowed:
                continue
            attacker = b.turn == cs.BLACK
            b.push(move)
            if not attacker or b.is_check():
                child = key(b)
                edges.append(dict(move=token,child=child))
                if child not in nodes:
                    nodes[child] = dict(sfen=b.sfen(),parent=state,move=token)
                    heapq.heappush(queue,(score(child),serial,child))
                    serial += 1
            b.pop()
        node['edges'] = edges
        expanded += 1
    path = []
    validation = None
    if found:
        state = found
        while nodes[state]['parent'] is not None:
            path.append(nodes[state]['move'])
            state = nodes[state]['parent']
        path.reverse()
        validation = validate(source['initial'], source['delayed_line']+path+suffix)
        assert validation['valid'] and key(shogi.Board(validation['final'])) == final_goal
    out = dict(scope=__doc__,pawn_transfer=args.pawn_transfer,allowed_piece_types=sorted(allowed),initial=source['initial'],prefix=source['delayed_line'],root=key(root),target=goal,final_target=final_goal,suffix=suffix,found=found,
               complete=not queue and not found and not cutoff,cutoff=cutoff,
               visited=len(nodes),frontier=len(queue),expanded_this_run=expanded,
               resumed_nodes=resumed,seconds=time.monotonic()-started,path=path,
               completion_source=str(args.goal_source) if args.goal_source else None,
               completion_goals=len(completion_goals),completion_goals_sha256=completion_hash,
               validation=validation,forced_cycle_certified=False,
               record_goal_achieved=False,nodes=nodes)
    if args.target_source:
        out['pawn_transfer'] = None
        out['exact_target_source'] = str(args.target_source)
    cache.write_bytes(gzip.compress(json.dumps(out).encode()))
    summary = {k:v for k,v in out.items() if k != 'nodes'}
    Path(stem+'.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
