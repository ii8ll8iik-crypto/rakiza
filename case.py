import os, sys, json, time, subprocess, requests

ROOT = "W4224073284"
DB = "case.rl"
MAILTO = os.environ.get("OPENALEX_MAILTO", "rakiza.project@example.com")
KEY = os.environ.get("OPENALEX_API_KEY")
FIELDS = "id,title,publication_year,publication_date,cited_by_count,referenced_works,is_retracted"

def get(url, **extra):
    p = {"select": FIELDS, "mailto": MAILTO, **extra}
    if KEY:
        p["api_key"] = KEY
    r = requests.get(url, params=p, timeout=60)
    if r.status_code != 200:
        sys.exit(f"خطأ {r.status_code} {r.text[:200]}")
    return r.json()

def rec(w):
    return {
        "title": w.get("title") or "",
        "year": w.get("publication_year") or 0,
        "date": w.get("publication_date") or "",
        "cites": w.get("cited_by_count") or 0,
        "retracted": bool(w.get("is_retracted")),
        "refs": [x.rsplit("/", 1)[-1] for x in (w.get("referenced_works") or [])],
    }

works = {ROOT: rec(get(f"https://api.openalex.org/works/{ROOT}"))}
cursor = "*"
while cursor:
    j = get("https://api.openalex.org/works", filter=f"cites:{ROOT}", **{"per-page": 200, "cursor": cursor})
    res = j.get("results", [])
    for w in res:
        works[w["id"].rsplit("/", 1)[-1]] = rec(w)
    cursor = j.get("meta", {}).get("next_cursor") if res else None
    print("جمعت", len(works) - 1, "ورقة مستشهِدة")
    time.sleep(0.3)
json.dump(works, open("case.json", "w"))

def q(s):
    return (s or "").replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")

def run(stmt):
    r = subprocess.run(["relate", "--database", DB, stmt], capture_output=True, text=True)
    if r.returncode != 0:
        print("خطأ", r.returncode, r.stderr[:300], "\n", stmt[:150])
        sys.exit(1)

if os.path.exists(DB):
    os.remove(DB)
items = list(works.items())
for i in range(0, len(items), 20):
    parts = [
        f"(:Paper {{id:'{wid}', title:'{q(w['title'])}', year:{w['year']}, date:'{w['date']}', cites:{w['cites']}, retracted:{str(w['retracted']).lower()}}})"
        for wid, w in items[i:i+20]
    ]
    run("CREATE " + ", ".join(parts))
print("الأوراق تمت")

ids = set(works)
edges = [(a, b) for a, w in works.items() if a != ROOT for b in w["refs"] if b in ids and b != a]
for i in range(0, len(edges), 15):
    batch = edges[i:i+15]
    nodes = sorted({x for e in batch for x in e})
    var = {n: f"p{k}" for k, n in enumerate(nodes)}
    match = ", ".join(f"({var[n]}:Paper {{id:'{n}'}})" for n in nodes)
    create = ", ".join(f"({var[a]})-[:CITES]->({var[b]})" for a, b in batch)
    run(f"MATCH {match} CREATE {create}")
print("خلص:", len(works) - 1, "مستشهِدة،", len(edges), "علاقة")
