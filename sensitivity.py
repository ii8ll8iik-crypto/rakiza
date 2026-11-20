import json, random
from collections import deque, defaultdict

with open("works.json", encoding="utf-8") as f:
    works = json.load(f)

all_nodes = sorted(works.keys())

def build_clean_adj(sub_ids):
    id_set = set(sub_ids)
    adj = {u: [] for u in sub_ids}
    for u in sub_ids:
        uy = int(works[u].get("year") or 0)
        seen = set()
        for v in works[u].get("refs", []):
            if v in id_set and v != u and v not in seen:
                seen.add(v)
                vy = int(works[v].get("year") or 0)
                if not (uy > 0 and vy > 0 and uy < vy):
                    adj[u].append(v)
    return adj

def compute_ablation(sub_ids):
    adj = build_clean_adj(sub_ids)
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
    base = {u: reach(u) for u in sub_ids}
    loss = {}
    for t in sub_ids:
        b_cnt = sum(len(base[u] - {t}) for u in sub_ids if u != t)
        n_cnt = sum(len(reach(u, blocked=t)) for u in sub_ids if u != t)
        loss[t] = b_cnt - n_cnt
    return loss

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

def tie_aware_spearman(full_map, sub_map):
    shared = sorted(sub_map.keys())
    n = len(shared)
    if n < 2:
        return 0.0
    r1 = average_ranks({k: full_map[k] for k in shared})
    r2 = average_ranks({k: sub_map[k] for k in shared})
    m1 = sum(r1.values()) / n
    m2 = sum(r2.values()) / n
    num = sum((r1[k] - m1) * (r2[k] - m2) for k in shared)
    den1 = sum((r1[k] - m1) ** 2 for k in shared) ** 0.5
    den2 = sum((r2[k] - m2) ** 2 for k in shared) ** 0.5
    return round(num / (den1 * den2), 4) if den1 and den2 else 0.0

by_year = defaultdict(list)
for wid, w in works.items():
    by_year[w.get("year", 0)].append((w.get("cites", 0), wid))

with open("ablation.json", encoding="utf-8") as f:
    full_loss = json.load(f)

top10_full = set(sorted(all_nodes, key=lambda x: full_loss[x], reverse=True)[:10])

scenarios = []
for k_yr in [20, 15, 10]:
    sub_ids = [wid for _, items in by_year.items() for _, wid in sorted(items, reverse=True)[:k_yr]]
    sloss = compute_ablation(sub_ids)
    top10_sub = set(sorted(sub_ids, key=lambda x: sloss[x], reverse=True)[:10])
    scenarios.append({
        "regime": f"top_{k_yr}_per_year",
        "nodes": len(sub_ids),
        "top10_overlap": len(top10_full & top10_sub),
        "spearman_tie_aware": tie_aware_spearman(full_loss, sloss),
    })

rng = random.Random(42)
rand_overlaps, rand_rhos = [], []
for _ in range(30):
    sub_ids = rng.sample(all_nodes, int(len(all_nodes) * 0.70))
    sloss = compute_ablation(sub_ids)
    top10_sub = set(sorted(sub_ids, key=lambda x: sloss[x], reverse=True)[:10])
    rand_overlaps.append(len(top10_full & top10_sub))
    rand_rhos.append(tie_aware_spearman(full_loss, sloss))

scenarios.append({
    "regime": "random_70pct_subsamples_30x",
    "nodes": int(len(all_nodes) * 0.70),
    "mean_top10_overlap": round(sum(rand_overlaps) / len(rand_overlaps), 2),
    "mean_spearman_tie_aware": round(sum(rand_rhos) / len(rand_rhos), 4),
})

report = {
    "graph_basis": "Temporally consistent subgraph (582 valid edges; 23 year-inverted edges excluded)",
    "full_sample_nodes": len(works),
    "year_counts": {str(y): len(v) for y, v in sorted(by_year.items())},
    "scenarios": scenarios,
}
with open("sensitivity.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
print(json.dumps(report, indent=2))
