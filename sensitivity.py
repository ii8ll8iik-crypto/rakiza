import json
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

by_year = defaultdict(list)
for wid, w in works.items():
    by_year[w.get("year", 0)].append((w.get("cites", 0), wid))

top15_ids = []
for y, items in by_year.items():
    for _, wid in sorted(items, reverse=True)[:15]:
        top15_ids.append(wid)

full_loss = json.load(open("ablation.json"))
sub_loss = compute_ablation(top15_ids)

top10_full = [k for k, _ in sorted(full_loss.items(), key=lambda x: x[1], reverse=True)[:10]]
top10_sub = [k for k, _ in sorted(sub_loss.items(), key=lambda x: x[1], reverse=True)[:10]]
overlap = set(top10_full) & set(top10_sub)

report = {
    "full_sample_nodes": len(works),
    "sub_sample_top15_per_year_nodes": len(top15_ids),
    "top10_chokepoints_overlap_count": len(overlap),
    "shared_top_chokepoints": [
        {"id": k, "title": works[k]["title"], "full_loss": full_loss[k], "sub15_loss": sub_loss[k]}
        for k in top10_full if k in overlap
    ]
}
json.dump(report, open("sensitivity.json", "w"), indent=2)
print(f"Sample Sensitivity: Top-25/yr (n={len(works)}) vs Top-15/yr (n={len(top15_ids)})")
print(f"Top-10 Chokepoint Stability: {len(overlap)}/10 papers remain in Top-10")
for item in report["shared_top_chokepoints"]:
    print(f"  - {item['title'][:65]} | full_loss={item['full_loss']} | top15_loss={item['sub15_loss']}")
