import json, os, re, threading, urllib.parse, urllib.request, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import audit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

def extract_identifiers(text):
    found = []
    seen = set()
    for m in re.finditer(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+|\bW\d{6,}\b", text or "", re.I):
        tok = m.group(0).rstrip(".,;})]>'\"")
        key = tok.upper() if tok.upper().startswith("W") else tok.lower()
        if key not in seen:
            seen.add(key)
            found.append(tok)
    return found

def load_json_if_exists(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None

def build_simulate_payload(wid):
    sim = audit.simulate_removal(wid)
    meta, adj = audit.load_live_graph()
    tid = sim["simulation_target"]["id"]
    base = {u: audit.reach(adj, u) for u in meta}
    down_ids, up_ids = set(), set()
    for u in meta:
        if u == tid:
            continue
        lost = (base[u] - {tid}) - audit.reach(adj, u, blocked=tid)
        if lost:
            down_ids.add(u)
            up_ids.update(lost)
    sim["affected_downstream_ids"] = sorted(down_ids)
    sim["disconnected_upstream_ids"] = sorted(up_ids)
    return sim

def run_grounded_agent(prompt, api_key="", provider="gemini", model_name=""):
    prompt = (prompt or "").strip()
    if not prompt:
        return {"error": "Please enter a question grounded in Rakiza's Relate databases."}

    ids = extract_identifiers(prompt)
    low = prompt.lower()

    # Optional external LLM tool-calling path (strictly grounded in Relate tool outputs)
    if api_key.strip():
        try:
            top_rows = audit.cypher_json(
                "graph.rl",
                "MATCH (p:Paper) RETURN p.id AS id, p.title AS title, p.year AS year, "
                "p.ablation_loss AS clean_ablation, p.ablation_raw AS raw_ablation, p.bridge AS bridge "
                "ORDER BY p.ablation_loss DESC LIMIT 5"
            )
            case_rows = audit.cypher_json(
                "case.rl",
                "MATCH (p:Paper) WHERE p.id <> 'W4224073284' "
                "RETURN p.temporal_tier AS tier, count(p) AS n ORDER BY n DESC"
            )
            context_obj = {
                "top_clean_chokepoints_graph_rl": top_rows,
                "retraction_tiers_case_rl_root_W4224073284": case_rows,
                "explicit_ids_in_prompt": ids,
            }
            if ids:
                context_obj["audited_ids"] = [audit.audit(x, live=False) for x in ids[:5]]

            sys_inst = (
                "You are Rakiza Agent, a strictly grounded research assistant backed ONLY by the provided "
                "Relate graph outputs (graph.rl and case.rl). Never invent IDs, counts, dates, or claims "
                "not present in the JSON context. If something is absent from the context, state that clearly."
            )
            user_msg = f"Context from Relate:\n{json.dumps(context_obj, ensure_ascii=False)}\n\nQuestion: {prompt}"

            if provider == "openai":
                m_id = model_name.strip() or "gpt-4o-mini"
                req = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=json.dumps({
                        "model": m_id,
                        "temperature": 0.1,
                        "messages": [{"role": "system", "content": sys_inst}, {"role": "user", "content": user_msg}]
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                answer = data["choices"][0]["message"]["content"]
            else:
                m_id = model_name.strip() or "gemini-2.5-flash"
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(m_id)}:generateContent?key={urllib.parse.quote(api_key.strip())}"
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps({
                        "systemInstruction": {"parts": [{"text": sys_inst}]},
                        "contents": [{"parts": [{"text": user_msg}]}],
                        "generationConfig": {"temperature": 0.1}
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                answer = data["candidates"][0]["content"]["parts"][0]["text"]

            sim_for_ui = None
            if ids and any(k in low for k in ["simulat", "remov", "ablat", "بتر", "إزال"]):
                try:
                    sim_for_ui = build_simulate_payload(ids[0])
                except Exception:
                    sim_for_ui = None
            return {
                "mode": f"llm-grounded ({provider}:{m_id})",
                "answer": answer,
                "cited_ids": ids,
                "facts": context_obj,
                "simulation": sim_for_ui,
            }
        except Exception as e:
            fallback = run_grounded_agent(prompt, api_key="")
            fallback["note"] = f"External LLM call fell back to local Relate agent: {e}"
            return fallback

    # Deterministic local Relate-grounded agent (zero API key required)
    top_rows = audit.cypher_json(
        "graph.rl",
        "MATCH (p:Paper) RETURN p.id AS id, p.title AS title, p.year AS year, "
        "p.ablation_loss AS clean_ablation, p.ablation_raw AS raw_ablation, round(p.bridge*10000)/10000.0 AS bridge "
        "ORDER BY p.ablation_loss DESC LIMIT 5"
    )
    tier_rows = audit.cypher_json(
        "case.rl",
        "MATCH (p:Paper) WHERE p.id <> 'W4224073284' "
        "RETURN p.temporal_tier AS tier, count(p) AS n ORDER BY n DESC"
    )

    # 1. Explicit IDs queried
    if ids:
        audits = []
        sim_payload = None
        for ident in ids[:5]:
            try:
                rep = audit.audit(ident, live=False)
                audits.append(rep)
                if sim_payload is None and ("simulat" in low or "remov" in low or "ablat" in low or "بتر" in low or "إزال" in low) and rep["main_corpus_graph_rl"]["present"]:
                    sim_payload = build_simulate_payload(rep["work_id"])
            except Exception as e:
                audits.append({"work_id": ident, "error": str(e)})

        lines = ["Grounded findings from Relate (graph.rl & case.rl):"]
        for r in audits:
            if "error" in r:
                lines.append(f"- {r['work_id']}: not resolved in local snapshot ({r['error']}).")
                continue
            mg = r["main_corpus_graph_rl"]
            cg = r["retraction_case_case_rl"]
            lines.append(
                f"- {r['work_id']} ({mg.get('title') or 'Untitled'}, {mg.get('year') or 'N/A'}) -> "
                f"Status: {r['status']} | Clean Ablation: {mg.get('ablation_lost_reachability_pairs')} "
                f"(Raw: {mg.get('ablation_raw_unfiltered')}) | 3-Hop Reach: {mg.get('structural_reach_3hop')} | "
                f"Case Tier: {cg.get('temporal_tier') or ('ROOT' if r['retracted_flag'] else 'none')} | "
                f"Post-12M+ Citers: {cg.get('post_12m_plus_citers')}."
            )
        if sim_payload:
            im = sim_payload["impact_metrics"]
            lines.append(
                f"Ablation simulation for {sim_payload['simulation_target']['id']}: "
                f"{im['lost_reachability_pairs_unbounded']} lost reachability pairs across "
                f"{im['affected_downstream_papers_count']} downstream papers."
            )
        return {
            "mode": "local-relate-agent",
            "answer": "\n".join(lines),
            "audits": audits,
            "simulation": sim_payload,
            "top_chokepoints": top_rows,
            "retraction_tiers": tier_rows,
        }

    # 2. Retraction / case.rl intent
    if any(k in low for k in ["retract", "case", "tier", "lag", "post_12m", "سحب", "مسحوب", "4224073284"]):
        tier_txt = ", ".join(f"{t['tier']}: {t['n']}" for t in tier_rows)
        return {
            "mode": "local-relate-agent",
            "answer": (
                "From case.rl (retracted root W4224073284, notice 2023-10-18, 372 citing papers): "
                f"temporal tier breakdown is [{tier_txt}]. "
                "This database scopes strictly to citations of W4224073284 and does not assert experimental dependence without full-text review."
            ),
            "retraction_tiers": tier_rows,
            "top_chokepoints": top_rows,
        }

    # 3. Chokepoint / ablation / top paper intent
    target_top = top_rows[0] if top_rows else None
    sim_payload = None
    if target_top and any(k in low for k in ["simulat", "remov", "ablat", "بتر", "إزال", "تأثير"]):
        sim_payload = build_simulate_payload(target_top["id"])

    summary_lines = [
        "Top temporally clean chokepoints in graph.rl (306 papers, 582 valid edges, 23 inverted edges flagged):"
    ]
    for idx, row in enumerate(top_rows, 1):
        summary_lines.append(
            f"{idx}. {row['title']} ({row['year']}, {row['id']}) — Clean Ablation: {row['clean_ablation']} "
            f"(Raw: {row['raw_ablation']}), Bridge: {row['bridge']}"
        )
    if sim_payload:
        im = sim_payload["impact_metrics"]
        summary_lines.append(
            f"\nSimulated removal of #1 chokepoint ({sim_payload['simulation_target']['id']}): "
            f"{im['lost_reachability_pairs_unbounded']} lost reachability pairs, "
            f"{im['affected_downstream_papers_count']} affected downstream papers."
        )

    return {
        "mode": "local-relate-agent",
        "answer": "\n".join(summary_lines),
        "top_chokepoints": top_rows,
        "retraction_tiers": tier_rows,
        "simulation": sim_payload,
    }

class RakizaHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, obj, status=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, path):
        with open(path, "rb") as f:
            raw = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path in ("/", "/index.html"):
                self._send_html(os.path.join(BASE_DIR, "index.html"))
            elif parsed.path == "/api/graph":
                nodes = audit.cypher_json(
                    "graph.rl",
                    "MATCH (p:Paper) RETURN p.id AS id, p.title AS title, p.year AS year, "
                    "p.cites AS cites, p.retracted AS retracted, p.bridge AS bridge, "
                    "p.pagerank AS pagerank, p.ablation_loss AS ablation_clean, p.ablation_raw AS ablation_raw"
                )
                edges = audit.cypher_json(
                    "graph.rl",
                    "MATCH (a:Paper)-[r:CITES]->(b:Paper) WHERE a.id <> b.id "
                    "RETURN a.id AS src, b.id AS dst, coalesce(r.temporal_valid, true) AS temporal_valid"
                )
                self._send_json({
                    "nodes": nodes,
                    "edges": edges,
                    "metrics_comparison": load_json_if_exists("metrics_comparison.json"),
                    "sensitivity": load_json_if_exists("sensitivity.json"),
                })
            elif parsed.path == "/api/case":
                nodes = audit.cypher_json(
                    "case.rl",
                    "MATCH (p:Paper) RETURN p.id AS id, p.title AS title, p.year AS year, "
                    "p.date AS date, p.cites AS cites, p.retracted AS retracted, p.temporal_tier AS tier"
                )
                edges = audit.cypher_json(
                    "case.rl",
                    "MATCH (a:Paper)-[:CITES]->(b:Paper) WHERE a.id <> b.id RETURN a.id AS src, b.id AS dst"
                )
                self._send_json({"nodes": nodes, "edges": edges})
            elif parsed.path == "/api/simulate":
                wid = (qs.get("id") or [""])[0].strip()
                self._send_json(build_simulate_payload(wid))
            else:
                self._send_json({"error": "Not found"}, 404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/api/audit", "/api/agent"):
            self._send_json({"error": "Not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")

            if parsed.path == "/api/agent":
                res_obj = run_grounded_agent(
                    body.get("prompt", ""),
                    api_key=body.get("api_key", ""),
                    provider=body.get("provider", "gemini"),
                    model_name=body.get("model", ""),
                )
                self._send_json(res_obj)
                return

            ids = extract_identifiers(body.get("text", ""))
            live = bool(body.get("add_live", False))
            if not ids:
                self._send_json({"error": "No valid OpenAlex Work IDs (W...) or DOIs found in input."}, 400)
                return
            results = []
            for ident in ids[:25]:
                try:
                    results.append({"ok": True, "input": ident, "report": audit.audit(ident, live=live)})
                except Exception as e:
                    results.append({"ok": False, "input": ident, "error": str(e)})
            self._send_json({"count": len(results), "results": results})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

if __name__ == "__main__":
    port = int(os.environ.get("RAKIZA_PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), RakizaHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"Rakiza Visual Studio running at {url}  (Press Ctrl+C to stop)")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Rakiza UI.")
        server.server_close()
