"""Build a finite closed defender strategy graph, then independently verify it.

Every Black checking move must remain in the graph. White selects one legal
reply. No White mating terminal is admitted. Finite closed cycles cannot prove
a forced finite mate, so cycles are valid NoMate evidence (unlike mate proofs).
Engine NoMate reports guide White choices only and are never proof leaves.
"""
import argparse
import json
import time
from collections import deque
from pathlib import Path
import cshogi as cs
import shogi
from synthesize import Engine
from orthodox_legal import legal_moves

def key(b):
    return ' '.join(b.sfen().split()[:3])

def checks(b):
    result = []
    for move in list(b.legal_moves):
        token = cs.move_to_usi(move)
        b.push(move)
        if b.is_check():
            result.append(token)
        b.pop()
    return result

def verify(initial, nodes):
    root = key(cs.Board(initial))
    pending = [root]
    visited = set()
    edges = 0
    terminals = 0
    countercheck_edges = {}
    while pending:
        state = pending.pop()
        if state in visited:
            continue
        visited.add(state)
        assert state in nodes
        node = nodes[state]
        b = shogi.Board(state+' 1')
        native = cs.Board(state+' 1')
        legal = {m.usi() for m in legal_moves(b)}
        assert legal == {cs.move_to_usi(m) for m in native.legal_moves}
        if b.turn == shogi.BLACK:
            wanted = set()
            for move in list(legal_moves(b)):
                b.push(move)
                if b.is_check():
                    wanted.add(move.usi())
                b.pop()
            assert wanted == set(node['attacks'])
            children = node['attacks']
            if not wanted:
                terminals += 1
        else:
            assert b.is_check() and legal, 'White mate cannot appear in a NoMate graph'
            assert node['reply'] in legal
            children = {node['reply']: node['next']}
        for token, child in children.items():
            b.push_usi(token)
            assert key(b) == child
            if b.turn == shogi.WHITE:
                assert b.is_check()
                countercheck_edges.setdefault(state, []).append(child)
            elif b.is_check():
                countercheck_edges.setdefault(state, []).append(child)
            b.pop()
            edges += 1
            pending.append(child)
    # Every full cycle must contain a White nonchecking reply. Otherwise a
    # cycle could rely on White's own continuous-check repetition violation.
    degree = {state: 0 for state in visited}
    for children in countercheck_edges.values():
        for child in children:
            degree[child] += 1
    ready = deque(state for state, value in degree.items() if value == 0)
    removed = 0
    while ready:
        state = ready.popleft()
        removed += 1
        for child in countercheck_edges.get(state, []):
            degree[child] -= 1
            if degree[child] == 0:
                ready.append(child)
    assert removed == len(visited), 'Countercheck-only cycle requires another defender strategy'
    return dict(reachable_nodes=len(visited), edges=edges,
        black_no_checks_terminals=terminals, closed=True,
        white_continuous_check_cycles_excluded=True,
        argument='All attacks covered, legal defender strategy never reaches mate; finite closed cycles permit no forced finite mate.')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--seconds', type=float, default=20)
    ap.add_argument('--nodes', type=int, default=10000)
    ap.add_argument('--defender-board-only', action='store_true', help='Seek a strategy without any defender drops')
    args = ap.parse_args()
    initial = json.loads(args.source.read_text())['initial']
    root = key(cs.Board(initial))
    nodes = {}
    queue = deque([root])
    known = {root}
    reports = {}
    if args.output.exists():
        old = json.loads(args.output.read_text())
        assert old['initial'] == initial and old['scope'] == __doc__
        assert old.get('defender_board_only',False)==args.defender_board_only
        if old['status'] == 'independently_certified_nomate':
            print('Saved certificate terminal; not rebuilding.')
            return
        nodes = old['nodes']
        queue = deque(old['frontier'])
        known = set(nodes) | set(queue)
        reports = old['oracle_reports']
    started = time.monotonic()
    engine = Engine()
    cutoff = None
    calls = 0
    unresolved_reply = None
    def add(state):
        if state not in known:
            known.add(state)
            queue.append(state)
    try:
        while queue:
            if time.monotonic()-started >= args.seconds or len(nodes) >= args.nodes:
                cutoff = 'budget'
                break
            state = queue.popleft()
            b = cs.Board(state+' 1')
            if b.turn == cs.BLACK:
                attacks = {}
                for token in checks(b):
                    b.push_usi(token)
                    child = key(b)
                    b.pop()
                    attacks[token] = child
                    add(child)
                nodes[state] = dict(attacks=attacks)
            else:
                options = []
                for move in list(b.legal_moves):
                    if args.defender_board_only and cs.move_is_drop(move):continue
                    token = cs.move_to_usi(move)
                    capture = bool(b.piece(cs.move_to(move)))
                    b.push(move)
                    child = key(b)
                    child_checks = checks(b)
                    options.append((child not in nodes, child not in known,
                        len(child_checks), b.is_check(), not capture, token, child))
                    b.pop()
                selected = None
                for _, _, count, reverse, capture, token, child in sorted(options):
                    if count == 0:
                        selected = (token, child)
                        break
                    if time.monotonic()-started >= args.seconds:
                        break
                    if child not in reports or reports[child] == 'timeout':
                        pv, log = engine.solve(child+' 1', 300 if reports.get(child) == 'timeout' else 30)
                        reports[child] = 'mate' if pv else log[-1].split()[1]
                        calls += 1
                    if reports[child] == 'nomate':
                        selected = (token, child)
                        break
                if selected is None:
                    queue.appendleft(state)
                    cutoff = ('budget during reply selection' if time.monotonic()-started >= args.seconds
                              else 'no guided candidate reply yet' if options else 'White mate encountered')
                    unresolved_reply = dict(state=state, options=[dict(move=token, child=child,
                        checking_attacks=count, countercheck=reverse,
                        oracle_report=reports.get(child))
                        for _, _, count, reverse, capture, token, child in sorted(options)])
                    break
                token, child = selected
                nodes[state] = dict(reply=token, next=child)
                add(child)
    finally:
        engine.close()
    out = dict(scope=__doc__, initial=initial, nodes=nodes,
        frontier=list(queue), oracle_reports=reports, cutoff=cutoff,
        status='unknown', engine_calls_this_run=calls,
        seconds=time.monotonic()-started, unresolved_reply=unresolved_reply, record_goal_achieved=False)
    if not queue:
        try:
            out['verification'] = verify(initial, nodes)
            out['status'] = 'independently_certified_nomate'
        except AssertionError as error:
            out['status'] = 'closed_graph_rejected'
            out['verification_failure'] = str(error)
    out['defender_board_only']=args.defender_board_only
    args.output.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k not in ['scope','nodes','oracle_reports','frontier']}), flush=True)
    print('nodes', len(nodes), 'pending', len(queue), flush=True)

if __name__ == '__main__':
    main()
