import json
import matplotlib.pyplot as plt

with open("metrics_comparison.json", encoding="utf-8") as f:
    mc = json.load(f)
with open("works.json", encoding="utf-8") as f:
    works = json.load(f)

top8 = mc["before_after_top10"][:8][::-1]
labels = [f"{r['title'][:36]}... ({r['year']})" if len(r["title"]) > 36 else f"{r['title']} ({r['year']})" for r in top8]
clean_vals = [r["ablation_clean"] for r in top8]
raw_vals = [r["ablation_raw"] for r in top8]

# Compute 3-hop temporally valid reach for the same 8 papers
adj_clean = {
    u: [v for v in w.get("refs", []) if v in works and v != u and not (int(works[u].get("year") or 0) > 0 and int(works[v].get("year") or 0) > 0 and int(works[u]["year"]) < int(works[v]["year"]))]
    for u, w in works.items()
}
reach3 = []
for r in top8:
    tid = r["id"]
    count = 0
    for src in works:
        if src == tid:
            continue
        frontier = {src}
        seen = {src}
        found = False
        for _ in range(3):
            nxt = set()
            for u in frontier:
                for v in adj_clean[u]:
                    if v == tid:
                        found = True
                    if v not in seen:
                        seen.add(v)
                        nxt.add(v)
            frontier = nxt
        if found:
            count += 1
    reach3.append(count)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2), dpi=160)
fig.patch.set_facecolor("white")
y = range(len(top8))
h = 0.36

ax1.barh([i + h/2 for i in y], clean_vals, height=h, color="#1f4e78", label="Clean Graph (582 valid edges)")
ax1.barh([i - h/2 for i in y], raw_vals, height=h, color="#a6bddb", label="Raw Unfiltered (605 edges)")
ax1.set_yticks(list(y))
ax1.set_yticklabels(labels, fontsize=8.5)
ax1.set_xlabel("Lost Directed Reachability Pairs on Node Removal")
ax1.set_title("Node Ablation Impact (Clean vs. Raw)")
ax1.legend(loc="lower right", fontsize=8)
ax1.grid(axis="x", linestyle="--", alpha=0.35)
for i, (cv, rv) in enumerate(zip(clean_vals, raw_vals)):
    ax1.text(cv + 4, i + h/2, str(cv), va="center", fontsize=7.5, fontweight="bold", color="#1f4e78")
    ax1.text(rv + 4, i - h/2, str(rv), va="center", fontsize=7.5, color="#4a607a")
ax1.set_xlim(0, max(raw_vals) * 1.16)

ax2.barh(list(y), reach3, height=0.52, color="#2e8b57")
ax2.set_yticks(list(y))
ax2.set_yticklabels([""] * len(top8))
ax2.set_xlabel("Citing Papers Within <=3 Hops (Temporally Valid)")
ax2.set_title("Bounded 3-Hop Structural Reach")
ax2.grid(axis="x", linestyle="--", alpha=0.35)
for i, v in enumerate(reach3):
    ax2.text(v + 0.8, i, str(v), va="center", fontsize=8, fontweight="bold", color="#2e8b57")
ax2.set_xlim(0, max(reach3) * 1.18)

fig.suptitle("Rakiza: Temporally Validated Chokepoints & 3-Hop Reach in Medical-Imaging AI (n=306)", fontsize=11.5, fontweight="bold")
plt.tight_layout()
plt.savefig("chart.png", bbox_inches="tight")
print("Updated chart.png with temporally cleaned metrics.")
