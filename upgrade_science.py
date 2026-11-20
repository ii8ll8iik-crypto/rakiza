import json, subprocess
from collections import deque

def run_rel(db, stmt, mode=None):
    cmd = ["relate", "--database", db] + (["--mode", mode] if mode else []) + [stmt]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout

# 1. التصنيف الزمني لعقد case.rl وحقن p.temporal_tier داخل Relate
rules = [
    ("AMBIGUOUS_DATE", "p.year = 0 OR p.date ENDS WITH '-01-01'"),
    ("PRE_NOTICE", "p.year > 0 AND NOT (p.date ENDS WITH '-01-01') AND p.date < '2023-10-18'"),
    ("LAG_0_6M", "NOT (p.date ENDS WITH '-01-01') AND p.date >= '2023-10-18' AND p.date < '2024-04-18'"),
    ("POST_6_12M", "NOT (p.date ENDS WITH '-01-01') AND p.date >= '2024-04-18' AND p.date < '2024-10-18'"),
    ("POST_12M_PLUS", "NOT (p.date ENDS WITH '-01-01') AND p.date >= '2024-10-18'"),
]
for tier, cond in rules:
    run_rel("case.rl", f"MATCH (p:Paper) WHERE p.id <> 'W4224073284' AND ({cond}) SET p.temporal_tier = '{tier}'")

print("=== التصنيف الزمني داخل case.rl ===")
print(run_rel("case.rl", "MATCH (p:Paper) WHERE p.id <> 'W4224073284' RETURN p.temporal_tier AS tier, count(p) AS count ORDER BY count DESC", "table"))

# 2. اختبار البتر البنيوي (Node Ablation) ببايثون القياسية وحقن p.ablation_loss
works = json.load(open("works.json"))
nodes = list(works.keys())
adj = {u: [v for v in w.get("refs", []) if v in works and v != u] for u, w in works.items()}

def reach(start, blocked=None):
    seen = {start}
    q = deque([start])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v != blocked and v not in seen:
                seen.add(v)
                q.append(v)
    seen.remove(start)
    return seen

base_reach = {u: reach(u) for u in nodes}
loss_map = {}
for target in nodes:
    base_other = sum(len(base_reach[u] - {target}) for u in nodes if u != target)
    new_other = sum(len(reach(u, blocked=target)) for u in nodes if u != target)
    broken = base_other - new_other
    loss_map[target] = broken
    run_rel("graph.rl", f"MATCH (p:Paper {{id:'{target}'}}) SET p.ablation_loss = {broken}")

json.dump(loss_map, open("ablation.json", "w"), indent=2)
print("=== أعلى 10 نقاط اختناق حقيقية عند إزالتها (Node Ablation) ===")
print(run_rel("graph.rl", "MATCH (p:Paper) RETURN p.title AS paper, p.year AS year, round(p.bridge*10000)/10000.0 AS bridge, p.ablation_loss AS broken_pairs ORDER BY p.ablation_loss DESC LIMIT 10", "table"))
