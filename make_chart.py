import json, networkx as nx, matplotlib.pyplot as plt

works = json.load(open("works.json"))
bc = json.load(open("bridge.json"))

G = nx.DiGraph()
G.add_nodes_from(works)
for wid, w in works.items():
    for b in w["refs"]:
        if b in works:
            G.add_edge(wid, b)

exposed = {}
for n in G.nodes():
    anc = set()
    frontier = {n}
    for _ in range(3):
        nxt = set()
        for u in frontier:
            nxt.update(G.predecessors(u))
        anc.update(nxt)
        frontier = nxt
    anc.discard(n)
    exposed[n] = len(anc)

top = sorted(works, key=lambda k: -bc[k])[:8]
labels = [f"{works[k]['title'][:34]}... ({works[k]['year']})" for k in top][::-1]
direct_vals = [G.in_degree(k) for k in top][::-1]
exposed_vals = [exposed[k] for k in top][::-1]
bridge_vals = [bc[k] * 10000 for k in top][::-1]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.5), sharey=True)
y = range(len(labels))

ax1.barh([i - 0.18 for i in y], direct_vals, height=0.35, label="Direct Citations (in-sample)", color="#4A777A")
ax1.barh([i + 0.18 for i in y], exposed_vals, height=0.35, label="3-Hop Exposure (<=3 hops)", color="#E07A5F")
for i, (d, e) in enumerate(zip(direct_vals, exposed_vals)):
    ax1.text(d + 0.8, i - 0.18, str(d), va="center", fontsize=8, color="#2B4648")
    ax1.text(e + 0.8, i + 0.18, str(e), va="center", fontsize=8, color="#9E4731", fontweight="bold")
ax1.set_xlim(0, max(exposed_vals) * 1.15)
ax1.set_yticks(list(y))
ax1.set_yticklabels(labels, fontsize=9)
ax1.set_xlabel("Paper Count")
ax1.set_title("Direct Citations vs. 3-Hop Exposure")
ax1.legend(loc="lower right", fontsize=8)
ax1.grid(axis="x", linestyle="--", alpha=0.4)

ax2.barh(list(y), bridge_vals, height=0.5, color="#3D405B")
for i, b in enumerate(bridge_vals):
    ax2.text(b + 0.6, i, f"{b:.1f}", va="center", fontsize=8, color="#3D405B", fontweight="bold")
ax2.set_xlim(0, max(bridge_vals) * 1.18)
ax2.set_xlabel("Betweenness Centrality (x 10^-4)")
ax2.set_title("Structural Bridge Score (Chokepoint)")
ax2.grid(axis="x", linestyle="--", alpha=0.4)

plt.suptitle("Rakiza: Structural Exposure & Bridge Analysis in Medical-Imaging AI (n=306)", fontsize=11, fontweight="bold")
plt.tight_layout()
plt.savefig("chart.png", dpi=180)
print("تم تحديث chart.png بنجاح")
