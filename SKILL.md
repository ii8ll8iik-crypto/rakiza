---
name: rakiza-citation-audit
description: Embedded Relate graph engine (graph.rl and case.rl) with CLI and stdio MCP server (mcp_server.py) for citation auditing, node-removal simulation, and dynamic graph expansion.
---

# Rakiza Citation & Structural Audit Skill

Run from `rakiza/`:

```bash
# 1. Batch audit for agents (JSON + citation chains + temporal tiers)
python3 audit.py W4224073284 10.1186/s13007-023-01096-w --json

# 2. Structural impact simulation (what breaks if a paper is removed?)
python3 audit.py <OPENALEX_ID_OR_DOI> --simulate

# 3. Dynamic live expansion with before/after reachability & chokepoint deltas
python3 audit.py <OPENALEX_ID_OR_DOI> --add-live --json

# 4. Run all 5 structural, ablation & temporal summary tables
python3 ask.py

# 5. Start standard stdio MCP server for AI coding/research agents
python3 mcp_server.py
```

## Epistemic Guardrails
- **Structural Reach vs. Research Dependence:** `graph.rl` (`n=306`) measures topological reach and node-ablation path loss; verifying full-text experimental reliance requires reading the citing paper.
- **Retraction Exposure Footprint:** `case.rl` (`n=372` citers of `W4224073284`, notice `2023-10-18`) classifies works into `POST_12M_PLUS` (`142`), `PRE_NOTICE` (`77`), `LAG_0_6M` (`69`), `POST_6_12M` (`53`), and `AMBIGUOUS_DATE` (`31`). Never infer author misconduct from publication timestamps alone.
