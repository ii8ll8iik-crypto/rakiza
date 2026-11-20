import os, re, sys, json, time, requests

QUERIES = [
    "deep learning medical image segmentation",
    "deep learning radiology",
    "convolutional neural network histopathology",
    "deep learning retinal fundus",
    "deep learning chest x-ray",
]
PER_YEAR = int(os.environ.get("PER_YEAR", "25"))
MAILTO = os.environ.get("OPENALEX_MAILTO", "rakiza.project@example.com")
FIELDS = "id,doi,title,publication_year,cited_by_count,referenced_works,is_retracted"

MED = re.compile(r"medical imag|biomedical imag|radiolog|radiograph|x-ray|mammogra|histopatholog|digital patholog|whole slide|\bMRI\b|\bCT\b|tomograph|ultrasound|fundus|retina|dermoscop|skin lesion|nodule|endoscop|\bOCT\b", re.I)
AI = re.compile(r"deep learning|deep neural|convolutional|neural network|machine learning|artificial intelligence|\bAI\b|\bCNN\b|U-?Net|transformer|computer-aided|computer aided|radiomics|foundation model|large language|segmentation|automated|automatic", re.I)

cands = {}
for year in range(2014, 2027):
    for q in QUERIES:
        params = {
            "search": q,
            "filter": f"publication_year:{year},type:article",
            "sort": "cited_by_count:desc",
            "per-page": 200,
            "select": FIELDS,
            "mailto": MAILTO,
        }
        key = os.environ.get("OPENALEX_API_KEY")
        if key:
            params["api_key"] = key
        r = requests.get("https://api.openalex.org/works", params=params, timeout=60)
        if r.status_code != 200:
            sys.exit(f"سنة {year}: خطأ {r.status_code} {r.text[:200]}")
        for w in r.json().get("results", []):
            title = w.get("title") or ""
            if not (MED.search(title) and AI.search(title)):
                continue
            wid = w["id"].rsplit("/", 1)[-1]
            cands[wid] = {
                "title": title,
                "year": w.get("publication_year") or 0,
                "cites": w.get("cited_by_count") or 0,
                "retracted": bool(w.get("is_retracted")),
                "refs": [x.rsplit("/", 1)[-1] for x in (w.get("referenced_works") or [])],
            }
        time.sleep(0.2)
    print(year, "-> مرشحين:", sum(1 for v in cands.values() if v["year"] == year))

works = {}
for year in range(2014, 2027):
    ys = sorted([(k, v) for k, v in cands.items() if v["year"] == year], key=lambda kv: -kv[1]["cites"])[:PER_YEAR]
    works.update(dict(ys))

ids = set(works)
edges = sum(1 for w in works.values() for b in w["refs"] if b in ids)
json.dump(works, open("works.json", "w"))
print("خلص:", len(works), "ورقة،", edges, "استشهاد داخل المجموعة")
