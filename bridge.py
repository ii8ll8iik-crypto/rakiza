import json, subprocess, networkx as nx

works = json.load(open("works.json"))
G = nx.DiGraph()
G.add_nodes_from(works)
for wid, w in works.items():
    for b in w["refs"]:
        if b in works:
            G.add_edge(wid, b)

bc = nx.betweenness_centrality(G)
direct = dict(G.in_degree())
top = sorted(works, key=lambda k: -bc[k])[:12]
print("bridge   direct  year  title")
for k in top:
    print(f"{bc[k]:.4f}  {direct[k]:6d}  {works[k]['year']}  {works[k]['title'][:80]}")
json.dump(bc, open("bridge.json", "w"))

# تخزين مقياس الجسر كخاصية داخل قاعدة بيانات Relate
items = list(bc.items())
for i in range(0, len(items), 25):
    batch = items[i:i+25]
    match = ", ".join(f"(p{k}:Paper {{id:'{wid}'}})" for k, (wid, _) in enumerate(batch))
    sets = ", ".join(f"p{k}.bridge = {val:.6f}" for k, (_, val) in enumerate(batch))
    subprocess.run(["relate", "--database", "graph.rl", f"MATCH {match} SET {sets}"], check=True)
print("تم تخزين مقياس الجسر داخل graph.rl بنجاح")
