import argparse, json, os, re, subprocess, sys, urllib.parse, urllib.request
from collections import Counter, deque

MAILTO = os.environ.get("OPENALEX_MAILTO", "rakiza.project@example.com")
KEY = os.environ.get("OPENALEX_API_KEY")

def q(s):
    return (s or "").replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")

def cypher_json(db, stmt):
    if not os.path.exists(db):
        raise FileNotFoundError(f"Relate database not found: {db}")
    r = subprocess.run(["relate", "--database", db, "--mode", "json", stmt], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Relate query failed on {db}: {(r.stderr or r.stdout).strip()}")
    raw = r.stdout.strip()
    if not raw:
        raise RuntimeError(f"Empty output from Relate on {db}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from Relate on {db}: {e}")
    if not isinstance(parsed, dict) or not isinstance(parsed.get("data"), list):
        raise RuntimeError(f"Unexpected Relate response schema on {db}")
    return parsed["data"]

def run_write(db, stmt):
    if not os.path.exists(db):
        raise FileNotFoundError(f"Relate database not found: {db}")
    r = subprocess.run(["relate", "--database", db, stmt], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Relate write failed on {db}: {(r.stderr or r.stdout).strip()}")

def scalar(db, stmt, key):
    rows = cypher_json(db, stmt)
    return int(rows[0].get(key) or 0) if rows else 0

def fetch_openalex(path):
    sep = "&" if "?" in path else "?"
    url = f"https://api.openalex.org/{path}{sep}select=id,title,publication_year,cited_by_count,referenced_works,is_retracted&mailto={urllib.parse.quote(MAILTO)}"
    if KEY:
        url += f"&api_key={urllib.parse.quote(KEY)}"
    req = urllib.request.Request(url, headers={"User-Agent": f"Rakiza/1.1 (mailto:{MAILTO})"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def resolve_id(ident):
    if not ident or not ident.strip():
        raise ValueError("Empty identifier provided")
    m = re.search(r"\b(W\d+)\b", ident.strip(), re.I)
    if m:
        return m.group(1).upper(), None
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", ident.strip(), flags=re.I)
    encoded = urllib.parse.quote(f"https://doi.org/{doi}", safe="")
    try:
        d = fetch_openalex(f"works/{encoded}")
        return d["id"].rsplit("/", 1)[-1], d
    except Exception as e:
        raise ValueError(f"OpenAlex lookup failed for '{ident}': {e}")

def load_live_graph():
    nodes_rows = cypher_json("graph.rl", "MATCH (p:Paper) RETURN p.id AS id, p.title AS title, p.year AS year, p.ablation_loss AS ablation")
    edges_rows = cypher_json("graph.rl", "MATCH (a:Paper)-[r:CITES]->(b:Paper) WHERE a.id <> b.id AND coalesce(r.temporal_valid, true) = true RETURN a.id AS src, b.id AS dst")
    meta = {r["id"]: r for r in nodes_rows}
    adj = {u: set() for u in meta}
    for e in edges_rows:
        if e["src"] in adj and e["dst"] in meta:
            adj[e["src"]].add(e["dst"])
    return meta, {u: list(vs) for u, vs in adj.items()}

def reach(adj, start, blocked=None):
    seen = {start}
    dq = deque([start])
    while dq:
        u = dq.popleft()
        for v in adj.get(u, ()):
            if v != blocked and v not in seen:
                seen.add(v)
                dq.append(v)
    seen.remove(start)
    return seen

def compute_all_ablation(adj):
    nodes = list(adj.keys())
    base = {u: reach(adj, u) for u in nodes}
    total_pairs = sum(len(v) for v in base.values())
    loss = {}
    for t in nodes:
        b_cnt = sum(len(base[u] - {t}) for u in nodes if u != t)
        n_cnt = sum(len(reach(adj, u, blocked=t)) for u in nodes if u != t)
        loss[t] = b_cnt - n_cnt
    return total_pairs, loss

def count_wcc(nodes, adj, blocked=None):
    active = [n for n in nodes if n != blocked]
    und = {n: set() for n in active}
    for u in active:
        for v in adj.get(u, ()):
            if v != blocked and v in und:
                und[u].add(v)
                und[v].add(u)
    visited, comps = set(), 0
    for n in active:
        if n not in visited:
            comps += 1
            dq = deque([n])
            visited.add(n)
            while dq:
                cur = dq.popleft()
                for nxt in und[cur]:
                    if nxt not in visited:
                        visited.add(nxt)
                        dq.append(nxt)
    return comps

def simulate_removal(ident):
    wid, _ = resolve_id(ident)
    meta, adj = load_live_graph()
    if wid not in meta:
        raise ValueError(f"Paper {wid} not present in graph.rl; use --add-live first.")
    nodes = list(meta.keys())
    base = {u: reach(adj, u) for u in nodes}
    severed_down, severed_up = Counter(), Counter()
    for u in nodes:
        if u == wid:
            continue
        lost = (base[u] - {wid}) - reach(adj, u, blocked=wid)
        if lost:
            severed_down[u] = len(lost)
            for v in lost:
                severed_up[v] += 1
    return {
        "simulation_target": {"id": wid, "title": meta[wid]["title"], "year": meta[wid]["year"]},
        "impact_metrics": {
            "lost_reachability_pairs_unbounded": sum(severed_down.values()),
            "affected_downstream_papers_count": len(severed_down),
            "isolated_upstream_references_count": len(severed_up),
            "weakly_connected_components_before": count_wcc(nodes, adj),
            "weakly_connected_components_after": count_wcc(nodes, adj, blocked=wid),
        },
        "top_affected_downstream_papers": [
            {"id": u, "title": meta[u]["title"], "year": meta[u]["year"], "lost_upstream_reach_targets": c}
            for u, c in severed_down.most_common(5)
        ],
        "top_disconnected_upstream_references": [
            {"id": v, "title": meta[v]["title"], "year": meta[v]["year"], "lost_downstream_citers": c}
            for v, c in severed_up.most_common(5)
        ],
    }

def add_live_dynamic(wid, d):
    if d is None:
        d = fetch_openalex(f"works/{wid}")
    meta_before, adj_before = load_live_graph()
    pairs_before, _ = compute_all_ablation(adj_before)
    wy = int(d.get("publication_year") or 0)

    stmts = [
        f"CREATE (:Paper {{id:'{wid}', title:'{q(d.get('title'))}', year:{wy}, "
        f"cites:{int(d.get('cited_by_count') or 0)}, retracted:{str(bool(d.get('is_retracted'))).lower()}, "
        f"bridge:0.0, pagerank:0.0, ablation_loss:0, ablation_raw:0}})"
    ]
    linked_out = 0
    for ref in [x.rsplit("/", 1)[-1] for x in (d.get("referenced_works") or [])]:
        if ref in meta_before and ref != wid:
            ry = int(meta_before[ref].get("year") or 0)
            tval = str(wy == 0 or ry == 0 or wy >= ry).lower()
            stmts.append(f"MATCH (a:Paper {{id:'{wid}'}}), (b:Paper {{id:'{ref}'}}) CREATE (a)-[:CITES {{temporal_valid:{tval}}}]->(b)")
            linked_out += 1

    linked_in = 0
    if os.path.exists("works.json"):
        with open("works.json", encoding="utf-8") as f:
            wmap = json.load(f)
        for existing_id, winfo in wmap.items():
            if existing_id in meta_before and existing_id != wid and wid in (winfo.get("refs") or []):
                ey = int(meta_before[existing_id].get("year") or 0)
                tval = str(ey == 0 or wy == 0 or ey >= wy).lower()
                stmts.append(f"MATCH (a:Paper {{id:'{existing_id}'}}), (b:Paper {{id:'{wid}'}}) CREATE (a)-[:CITES {{temporal_valid:{tval}}}]->(b)")
                linked_in += 1

    for s in stmts:
        run_write("graph.rl", s)

    meta_after, adj_after = load_live_graph()
    pairs_after, loss_after = compute_all_ablation(adj_after)
    shifted = []
    for nid, new_val in loss_after.items():
        old_val = int(meta_after[nid].get("ablation") or 0)
        if new_val != old_val:
            run_write("graph.rl", f"MATCH (p:Paper {{id:'{nid}'}}) SET p.ablation_loss = {new_val}")
            if nid != wid:
                shifted.append({"id": nid, "title": meta_after[nid]["title"], "ablation_before": old_val, "ablation_after": new_val})

    return {
        "added_node": wid,
        "outgoing_refs_linked_in_sample": linked_out,
        "incoming_citers_linked_from_snapshot": linked_in,
        "reachability_pairs_before": pairs_before,
        "reachability_pairs_after": pairs_after,
        "net_reachability_pairs_delta": pairs_after - pairs_before,
        "new_node_ablation_loss": loss_after.get(wid, 0),
        "scope_note": "Updates graph.rl edges and unbounded ablation_loss; bridge/pagerank remain 0.0 (not_computed) and case.rl is unchanged.",
        "updated_chokepoints": sorted(shifted, key=lambda x: x["ablation_after"] - x["ablation_before"], reverse=True)[:5],
    }

def get_chains(db, wid, direction="upstream"):
    tfilter = "AND coalesce(r1.temporal_valid, true) = true" if db == "graph.rl" else ""
    tfilter2 = "AND coalesce(r2.temporal_valid, true) = true" if db == "graph.rl" else ""
    if direction == "upstream":
        stmt = (f"MATCH (p:Paper {{id:'{wid}'}})-[r1:CITES]->(m:Paper) WHERE p.id <> m.id {tfilter} "
                f"OPTIONAL MATCH (m)-[r2:CITES]->(g:Paper) WHERE m.id <> g.id {tfilter2} "
                f"RETURN p.title AS s0, m.title AS s1, m.year AS y1, g.title AS s2, g.year AS y2 LIMIT 3")
    else:
        stmt = (f"MATCH (c1:Paper)-[r1:CITES]->(p:Paper {{id:'{wid}'}}) WHERE c1.id <> p.id {tfilter} "
                f"OPTIONAL MATCH (c2:Paper)-[r2:CITES]->(c1) WHERE c2.id <> c1.id {tfilter2} "
                f"RETURN c2.title AS s2, c2.year AS y2, c1.title AS s1, c1.year AS y1, p.title AS s0 LIMIT 3")
    out = []
    for r in cypher_json(db, stmt):
        if r.get("s1"):
            out.append(f"{r['s0']} -> {r['s1']} ({r.get('y1')})" + (f" -> {r['s2']} ({r.get('y2')})" if r.get("s2") else "") if direction == "upstream"
                       else (f"{r['s2']} ({r.get('y2')}) -> " if r.get("s2") else "") + f"{r['s1']} ({r.get('y1')}) -> {r['s0']}")
    return out

def audit(ident, live=False):
    wid, meta = resolve_id(ident)
    rows = cypher_json("graph.rl", f"MATCH (p:Paper {{id:'{wid}'}}) RETURN p.title AS title, p.year AS year, p.retracted AS retracted, p.bridge AS bridge, p.pagerank AS pagerank, p.ablation_loss AS ablation, p.ablation_raw AS ablation_raw")
    delta = add_live_dynamic(wid, meta) if (not rows and live) else None
    if delta is not None:
        rows = cypher_json("graph.rl", f"MATCH (p:Paper {{id:'{wid}'}}) RETURN p.title AS title, p.year AS year, p.retracted AS retracted, p.bridge AS bridge, p.pagerank AS pagerank, p.ablation_loss AS ablation, p.ablation_raw AS ablation_raw")
    in_main = bool(rows)
    info = rows[0] if in_main else {}

    case_rows = cypher_json("case.rl", f"MATCH (p:Paper {{id:'{wid}'}}) RETURN p.title AS title, p.year AS year, p.date AS date, p.retracted AS retracted, p.temporal_tier AS tier")
    in_case = bool(case_rows)
    cinfo = case_rows[0] if in_case else {}

    retracted = bool(info.get("retracted")) or bool(cinfo.get("retracted"))
    cites_root = scalar("case.rl", f"MATCH (a:Paper {{id:'{wid}'}})-[:CITES]->(:Paper {{id:'W4224073284'}}) RETURN count(a) AS n", "n") > 0
    direct = scalar("graph.rl", f"MATCH (d:Paper)-[r:CITES]->(p:Paper {{id:'{wid}'}}) WHERE d.id <> p.id AND coalesce(r.temporal_valid, true) = true RETURN count(DISTINCT d) AS n", "n")
    reach_3 = scalar("graph.rl", f"MATCH (a:Paper)-[r:CITES*1..3]->(p:Paper {{id:'{wid}'}}) WHERE a.id <> p.id AND ALL(rel IN r WHERE coalesce(rel.temporal_valid, true) = true) RETURN count(DISTINCT a) AS n", "n")
    ablation = info.get("ablation")

    status = ("RETRACTED_WORK" if retracted else ("RETRACTION_EXPOSURE_FOOTPRINT" if cites_root else
              ("HIGH_STRUCTURAL_CHOKEPOINT_OR_REACH" if ((ablation is not None and int(ablation) >= 80) or reach_3 >= 15) else
               ("PRESENT_IN_MAIN_CORPUS" if in_main else "OUTSIDE_LOCAL_SUBGRAPHS"))))

    chains = get_chains("graph.rl", wid, "upstream") if in_main else (get_chains("case.rl", wid, "upstream") if in_case else [])
    if in_main and not chains:
        chains = get_chains("graph.rl", wid, "downstream")

    return {
        "work_id": wid, "status": status, "retracted_flag": retracted, "cites_retracted_case_root_W4224073284": cites_root,
        "main_corpus_graph_rl": {
            "present": in_main, "dynamic_graph_delta": delta,
            "title": info.get("title") or cinfo.get("title") or (meta.get("title") if isinstance(meta, dict) else ""),
            "year": info.get("year") or cinfo.get("year") or (meta.get("publication_year") if isinstance(meta, dict) else None),
            "bridge_centrality": info.get("bridge"), "pagerank": info.get("pagerank"),
            "ablation_lost_reachability_pairs": ablation, "ablation_raw_unfiltered": info.get("ablation_raw"),
            "direct_citations_in_sample": direct, "structural_reach_3hop": reach_3,
        },
        "retraction_case_case_rl": {
            "present": in_case, "temporal_tier": cinfo.get("tier"), "indexed_pub_date": cinfo.get("date"),
            "total_citers_in_case": scalar("case.rl", f"MATCH (a:Paper)-[:CITES]->(:Paper {{id:'{wid}'}}) RETURN count(a) AS n", "n"),
            "post_12m_plus_citers": scalar("case.rl", f"MATCH (a:Paper)-[:CITES]->(:Paper {{id:'{wid}'}}) WHERE a.temporal_tier = 'POST_12M_PLUS' RETURN count(a) AS n", "n"),
            "lag_0_6m_citers": scalar("case.rl", f"MATCH (a:Paper)-[:CITES]->(:Paper {{id:'{wid}'}}) WHERE a.temporal_tier = 'LAG_0_6M' RETURN count(a) AS n", "n"),
        },
        "sample_citation_chains": chains,
        "confidence_and_limits": {
            "evidence_basis": "Scoped to temporally consistent graph.rl (n=306, 582 valid edges; 23 year-inverted edges excluded) and case.rl (n=372 citers of W4224073284).",
            "metric_definitions": "structural_reach_3hop is bounded to <=3 hops; ablation_lost_reachability_pairs evaluates unbounded directed reachability across temporally valid edges.",
            "epistemic_boundary": "Measures topological reach and citation paths, not full-text research dependence or author misconduct.",
        },
    }

def fmt(o):
    mg, cg = o["main_corpus_graph_rl"], o["retraction_case_case_rl"]
    lines = [
        f"Work ID: {o['work_id']} | Status: {o['status']}",
        f"Title  : {mg['title']} ({mg['year']})",
        f"[graph.rl] present={mg['present']} | ablation_clean={mg['ablation_lost_reachability_pairs']} (raw={mg['ablation_raw_unfiltered']}) | bridge={mg['bridge_centrality']} | direct={mg['direct_citations_in_sample']} | reach_3hop={mg['structural_reach_3hop']}",
        f"[case.rl]  present={cg['present']} | tier={cg['temporal_tier']} | total_citers={cg['total_citers_in_case']} | post_12m+={cg['post_12m_plus_citers']} | lag_0_6m={cg['lag_0_6m_citers']}",
    ]
    if mg.get("dynamic_graph_delta"):
        d = mg["dynamic_graph_delta"]
        lines.append(f"[Dynamic Delta] out_links={d['outgoing_refs_linked_in_sample']} | in_links={d['incoming_citers_linked_from_snapshot']} | net_reach_pairs_delta=+{d['net_reachability_pairs_delta']}")
    if o["sample_citation_chains"]:
        lines.append("Chains : " + " || ".join(o["sample_citation_chains"][:2]))
    return "\n".join(lines)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Rakiza contextual citation, simulation & dynamic audit engine.")
    ap.add_argument("identifiers", nargs="+", help="One or more OpenAlex Work IDs (W...) or DOIs")
    ap.add_argument("--json", action="store_true", help="Output structured JSON for AI agents")
    ap.add_argument("--add-live", action="store_true", help="Dynamically insert missing papers and recompute graph deltas")
    ap.add_argument("--simulate", action="store_true", help="Simulate removing the paper and list affected downstream works")
    args = ap.parse_args()
    try:
        if args.simulate:
            sims = [simulate_removal(i) for i in args.identifiers]
            out = sims[0] if len(sims) == 1 else {"simulations": sims}
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            reps = [audit(i, args.add_live) for i in args.identifiers]
            out = reps[0] if len(reps) == 1 else {"audited_count": len(reps), "results": reps}
            print(json.dumps(out, indent=2, ensure_ascii=False) if args.json else "\n---\n".join(fmt(r) for r in reps))
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        sys.exit(f"Error: {e}")
