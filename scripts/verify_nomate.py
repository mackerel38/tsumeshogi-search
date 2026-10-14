"""Verify a closed defender strategy; no engine oracle needed."""
import json,sys
from pathlib import Path
from collections import deque
import shogi,cshogi as cs
def key(b): return " ".join(b.sfen().split()[:3])
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
        legal = {m.usi() for m in b.legal_moves}
        assert legal == {cs.move_to_usi(m) for m in native.legal_moves}
        if b.turn == shogi.BLACK:
            wanted = set()
            for move in list(b.legal_moves):
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

if __name__=="__main__":
 d=json.loads(Path(sys.argv[1]).read_text()); print(json.dumps(verify(d["initial"],d["nodes"])))
