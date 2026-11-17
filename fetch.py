import os, sys, json, time, requests

QUERY = os.environ.get("QUERY", "deep learning medical imaging")
PER_YEAR = int(os.environ.get("PER_YEAR", "25"))
FIELDS = "id,doi,title,publication_year,cited_by_count,referenced_works,is_retracted"

works = {}
for year in range(2014, 2027):
    params = {
        "search": QUERY,
        "filter": f"publication_year:{year},type:article",
        "sort": "cited_by_count:desc",
        "per-page": PER_YEAR,
        "select": FIELDS,
        "mailto": "rakiza.project@example.com",
    }
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        params["api_key"] = key

    r = requests.get("https://api.openalex.org/works", params=params, timeout=60)
    if r.status_code != 200:
        sys.exit(f"سنة {year}: خطأ {r.status_code} {r.text[:200]}")
    for w in r.json().get("results", []):
        wid = w["id"].rsplit("/", 1)[-1]
        works[wid] = {
            "title": w.get("title") or "",
            "year": w.get("publication_year") or 0,
            "cites": w.get("cited_by_count") or 0,
            "retracted": bool(w.get("is_retracted")),
            "refs": [x.rsplit("/", 1)[-1] for x in (w.get("referenced_works") or [])],
        }
    print(year, "->", len(works), "ورقة")
    time.sleep(0.3)

ids = set(works)
edges = sum(1 for w in works.values() for b in w["refs"] if b in ids)
json.dump(works, open("works.json", "w"))
print("خلص:", len(works), "ورقة،", edges, "استشهاد داخل المجموعة")
