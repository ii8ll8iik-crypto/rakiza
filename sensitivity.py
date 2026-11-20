import json, random
from collections import deque, defaultdict

works = json.load(open("works.json"))

def compute_ablation(sub_ids):
    id_set = set(sub_ids)
    adj = {u: [v for v in works[u].get("refs", []) if v in id_set and v != u] for u in sub_ids}
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

def spearman_rho(full_map, sub_map):
    shared = [k for k in sub_map if k in full_map]
    n = len(shared)
    if n < 2:
        return 0.0
    r_full = {k: i for i, k in enumerate(sorted(shared, key=lambda x: full_map[x], reverse=True))}
    r_sub = {k: i for i, k in enumerate(sorted(shared, key=lambda x: sub_map[x], reverse=True))}
    d2 = sum((r_full[k] - r_sub[k]) ** 2 for k in shared)
    return round(1.0 - (6.0 * d2) / (n * (n**2 - 1)), 4)

by_year = defaultdict(list)
for wid, w in works.items():
    by_year[w.get("year", 0)].append((w.get("cites", 0), wid))

full_loss = json.load(open("ablation.json"))
top10_full = [k for k, _ in sorted(full_loss.items(), key=lambda x: x[1], reverse=True)[:10]]

scenarios = []
for k_yr in [20, 15, 10]:
    sub_ids = [wid for _, items in by_year.items() for _, wid in sorted(items, reverse=True)[:k_yr]]
    sloss = compute_ablation(sub_ids)
    top10_sub = [k for k, _ in sorted(sloss.items(), key=lambda x: x[1], reverse=True)[:10]]
    scenarios.append({
        "regime": f"top_{k_yr}_per_year",
        "nodes": len(sub_ids),
        "top10_overlap": len(set(top10_full) & set(top10_sub)),
        "spearman_rank_corr": spearman_rho(full_loss, sloss),
    })

rng = random.Random(42)
all_ids = sorted(works.keys())
rand_overlaps, rand_rhos = [], []
for seed_idx in range(5):
    sub_ids = rng.sample(all_ids, int(len(all_ids) * 0.70))
    sloss = compute_ablation(sub_ids)
    top10_sub = [k for k, _ in sorted(sloss.items(), key=lambda x: x[1], reverse=True)[:10]]
    rand_overlaps.append(len(set(top10_full) & set(top10_sub)))
    rand_rhos.append(spearman_rho(full_loss, sloss))

scenarios.append({
    "regime": "random_70pct_subsamples_5x",
    "nodes": int(len(all_ids) * 0.70),
    "mean_top10_overlap": round(sum(rand_overlaps) / len(rand_overlaps), 2),
    "mean_spearman_rank_corr": round(sum(rand_rhos) / len(rand_rhos), 4),
})

report = {
    "full_sample_nodes": len(works),
    "year_counts": {str(y): len(v) for y, v in sorted(by_year.items())},
    "scenarios": scenarios,
}
json.dump(report, open("sensitivity.json", "w"), indent=2)
print(json.dumps(report, indent=2))
