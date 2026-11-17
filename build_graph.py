import json, subprocess, sys

DB = "graph.rl"
works = json.load(open("works.json"))
ids = set(works)

def q(s):
    return (s or "").replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")

def run(stmt):
    r = subprocess.run(["relate", "--database", DB, stmt], capture_output=True, text=True)
    if r.returncode != 0:
        print("خطأ", r.returncode, r.stderr[:300], "\n", stmt[:150])
        sys.exit(1)

items = list(works.items())
for i in range(0, len(items), 20):
    parts = [
        f"(:Paper {{id:'{wid}', title:'{q(w['title'])}', year:{w['year']}, cites:{w['cites']}, retracted:{str(w['retracted']).lower()}}})"
        for wid, w in items[i:i+20]
    ]
    run("CREATE " + ", ".join(parts))
print("الأوراق تمت")

edges = [(a, b) for a, w in works.items() for b in w["refs"] if b in ids]
for i in range(0, len(edges), 15):
    batch = edges[i:i+15]
    nodes = sorted({x for e in batch for x in e})
    var = {n: f"p{k}" for k, n in enumerate(nodes)}
    match = ", ".join(f"({var[n]}:Paper {{id:'{n}'}})" for n in nodes)
    create = ", ".join(f"({var[a]})-[:CITES]->({var[b]})" for a, b in batch)
    run(f"MATCH {match} CREATE {create}")
print("خلص:", len(edges), "استشهاد")
