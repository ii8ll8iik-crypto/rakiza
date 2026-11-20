import json, subprocess
from collections import deque

def run_rel(db, stmt, mode=None):
    cmd = ["relate", "--database", db] + (["--mode", mode] if mode else []) + [stmt]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout

# 1. Assign temporal tiers inside case.rl
rules = [
    ("AMBIGUOUS_DATE", "p.year = 0 OR p.date ENDS WITH '-01-01'"),
    ("PRE_NOTICE", "p.year > 0 AND NOT (p.date ENDS WITH '-01-01') AND p.date < '2023-10-18'"),
    ("LAG_0_6M", "NOT (p.date ENDS WITH '-01-01') AND p.date >= '2023-10-18' AND p.date < '2024-04-18'"),
    ("POST_6_12M", "NOT (p.date ENDS WITH '-01-01') AND p.date >= '2024-04-18' AND p.date < '2024-10-18'"),
    ("POST_12M_PLUS", "NOT (p.date ENDS WITH '-01-01') AND p.date >= '2024-10-18'"),
]
for tier, cond in rules:
    run_rel("case.rl", f"MATCH (p:Paper) WHERE p.id <> 'W4224073284' AND ({cond}) SET p.temporal_tier = '{tier}'")

# 2. Load works.json and separate temporally valid vs. inverted edges (citing_year < cited_year)
with open("works.json", encoding="utf-8") as f:
    works = json.load(f)
with open("bridge.json", encoding="utf-8") as f:
    bridge_map = json.load(f)

nodes = sorted(works.keys())
adj_raw = {u: [] for u in nodes}
adj_clean = {u: [] for u in nodes}
inverted_edges = []

for u in nodes:
    uy = int(works[u].get("year") or 0)
    seen_targets = set()
    for v in works[u].get("refs", []):
        if v in works and v != u and v not in seen_targets:
            seen_targets.add(v)
            adj_raw[u].append(v)
            vy = int(works[v].get("year") or 0)
            if uy > 0 and vy > 0 and uy < vy:
                inverted_edges.append({"src": u, "src_year": uy, "dst": v, "dst_year": vy})
            else:
                adj_clean[u].append(v)

def compute_ablation(adj):
    def reach(start, blocked=None):
        seen = {start}
        q = deque([start])
        while q:
            cur = q.popleft()
            for nxt in adj[cur]:
                if nxt != blocked and nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        seen.remove(start)
        return seen
    base = {u: reach(u) for u in nodes}
    loss = {}
    for t in nodes:
        b_cnt = sum(len(base[u] - {t}) for u in nodes if u != t)
        n_cnt = sum(len(reach(u, blocked=t)) for u in nodes if u != t)
        loss[t] = b_cnt - n_cnt
    return loss

def compute_pagerank(adj, d=0.85, iters=100):
    n = len(nodes)
    pr = {u: 1.0 / n for u in nodes}
    for _ in range(iters):
        nxt = {u: (1.0 - d) / n for u in nodes}
        dangling = sum(pr[u] for u in nodes if not adj[u])
        for u in nodes:
            nxt[u] += d * dangling / n
            if adj[u]:
                share = d * pr[u] / len(adj[u])
                for v in adj[u]:
                    nxt[v] += share
        pr = nxt
    return pr

def average_ranks(val_map):
    items = sorted(val_map.items(), key=lambda x: x[1], reverse=True)
    ranks = {}
    i = 0
    while i < len(items):
        j = i
        while j + 1 < len(items) and items[j + 1][1] == items[i][1]:
            j += 1
        avg_r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[items[k][0]] = avg_r
        i = j + 1
    return ranks

def tie_aware_spearman(m1, m2):
    r1, r2 = average_ranks(m1), average_ranks(m2)
    n = len(nodes)
    mean1 = sum(r1.values()) / n
    mean2 = sum(r2.values()) / n
    num = sum((r1[u] - mean1) * (r2[u] - mean2) for u in nodes)
    den1 = sum((r1[u] - mean1) ** 2 for u in nodes) ** 0.5
    den2 = sum((r2[u] - mean2) ** 2 for u in nodes) ** 0.5
    return round(num / (den1 * den2), 4) if den1 and den2 else 0.0

loss_raw = compute_ablation(adj_raw)
loss_clean = compute_ablation(adj_clean)
pagerank_clean = compute_pagerank(adj_clean)
in_cites_clean = {u: sum(1 for src in nodes if u in adj_clean[src]) for u in nodes}
bridge_clean = {u: float(bridge_map.get(u, 0.0)) for u in nodes}

# 3. Tag edges and inject clean vs raw ablation & PageRank into graph.rl
run_rel("graph.rl", "MATCH (a:Paper)-[r:CITES]->(b:Paper) SET r.temporal_valid = (a.year = 0 OR b.year = 0 OR a.year >= b.year)")
for u in nodes:
    run_rel("graph.rl", f"MATCH (p:Paper {{id:'{u}'}}) SET p.ablation_loss = {loss_clean[u]}, p.ablation_raw = {loss_raw[u]}, p.pagerank = {pagerank_clean[u]:.8f}")

with open("ablation.json", "w", encoding="utf-8") as f:
    json.dump(loss_clean, f, indent=2)

metrics = {
    "in_cites_clean": in_cites_clean,
    "pagerank_clean": pagerank_clean,
    "betweenness": bridge_clean,
    "ablation_clean": loss_clean,
}
top10_sets = {k: set(sorted(nodes, key=lambda u: m[u], reverse=True)[:10]) for k, m in metrics.items()}
pairwise = {}
for m1 in metrics:
    pairwise[m1] = {}
    for m2 in metrics:
        pairwise[m1][m2] = {
            "spearman_tie_aware": tie_aware_spearman(metrics[m1], metrics[m2]),
            "top10_overlap": len(top10_sets[m1] & top10_sets[m2]),
        }

top10_raw = sorted(nodes, key=lambda u: loss_raw[u], reverse=True)[:10]
top10_clean = sorted(nodes, key=lambda u: loss_clean[u], reverse=True)[:10]
comp_report = {
    "total_edges": sum(len(v) for v in adj_raw.values()),
    "temporally_valid_edges": sum(len(v) for v in adj_clean.values()),
    "temporally_inverted_edges": len(inverted_edges),
    "top10_overlap_raw_vs_clean": len(set(top10_raw) & set(top10_clean)),
    "before_after_top10": [
        {"id": u, "title": works[u]["title"], "year": works[u]["year"], "ablation_raw": loss_raw[u], "ablation_clean": loss_clean[u]}
        for u in top10_clean
    ],
    "pairwise_metric_comparison": pairwise,
}
with open("metrics_comparison.json", "w", encoding="utf-8") as f:
    json.dump(comp_report, f, indent=2)

print(f"Edges: total={comp_report['total_edges']}, valid={comp_report['temporally_valid_edges']}, inverted={comp_report['temporally_inverted_edges']}")
print(f"Top-10 overlap (raw vs. temporally cleaned): {comp_report['top10_overlap_raw_vs_clean']}/10")
print("Spearman (clean ablation vs betweenness):", pairwise["ablation_clean"]["betweenness"])
print("Spearman (clean ablation vs pagerank)   :", pairwise["ablation_clean"]["pagerank_clean"])
print("Spearman (clean ablation vs in_cites)   :", pairwise["ablation_clean"]["in_cites_clean"])
print("\n=== Top 10 Chokepoints (Temporally Consistent Graph) ===")
print(run_rel("graph.rl", "MATCH (p:Paper) RETURN p.title AS paper, p.year AS year, round(p.bridge*10000)/10000.0 AS bridge, p.ablation_loss AS clean_ablation, p.ablation_raw AS raw_ablation ORDER BY p.ablation_loss DESC LIMIT 10", "table"))
