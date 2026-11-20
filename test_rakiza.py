import json, subprocess, unittest
from collections import Counter
import audit

class TestRakizaIntegrity(unittest.TestCase):
    def test_ablation_math_reproduces_covid_chokepoint(self):
        with open("works.json", encoding="utf-8") as f:
            works = json.load(f)
        adj = {u: [v for v in w.get("refs", []) if v in works and v != u] for u, w in works.items()}
        _, loss = audit.compute_all_ablation(adj)
        covid_ids = [k for k, w in works.items() if "Automated detection of COVID-19 cases" in w.get("title", "")]
        self.assertEqual(len(works), 306)
        self.assertEqual(len(covid_ids), 1)
        self.assertEqual(loss[covid_ids[0]], 344)

    def test_temporal_tiers_reproduce_exact_counts(self):
        with open("case.json", encoding="utf-8") as f:
            case = json.load(f)
        counts = Counter()
        for wid, w in case.items():
            if wid == "W4224073284":
                continue
            y, d = int(w.get("year") or 0), w.get("date") or ""
            if y == 0 or d.endswith("-01-01"):
                counts["AMBIGUOUS_DATE"] += 1
            elif d < "2023-10-18":
                counts["PRE_NOTICE"] += 1
            elif d < "2024-04-18":
                counts["LAG_0_6M"] += 1
            elif d < "2024-10-18":
                counts["POST_6_12M"] += 1
            else:
                counts["POST_12M_PLUS"] += 1
        self.assertEqual(dict(counts), {
            "POST_12M_PLUS": 142, "PRE_NOTICE": 77, "LAG_0_6M": 69, "POST_6_12M": 53, "AMBIGUOUS_DATE": 31
        })

    def test_cypher_json_raises_on_missing_db(self):
        with self.assertRaises(FileNotFoundError):
            audit.cypher_json("nonexistent_db.rl", "MATCH (n) RETURN n")

    def test_mcp_server_survives_invalid_doi_and_answers_ping(self):
        payload = (
            '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"audit_citations","arguments":{"identifiers":["10.9999/invalid-nonexistent-rakiza-test"]}}}\n'
            '{"jsonrpc":"2.0","id":2,"method":"ping"}\n'
        )
        proc = subprocess.run(["python3", "mcp_server.py"], input=payload, capture_output=True, text=True, timeout=25)
        self.assertEqual(proc.returncode, 0)
        lines = [json.loads(x) for x in proc.stdout.strip().splitlines() if x.strip()]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0]["result"]["isError"])
        self.assertEqual(lines[1], {"jsonrpc": "2.0", "id": 2, "result": {}})

if __name__ == "__main__":
    unittest.main()
