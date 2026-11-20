# Rakiza (ركيزة)
**Embedded Relate graph context engine & MCP server for researchers and AI agents to audit 3-hop structural reach, simulate unbounded node-ablation impact, and trace retraction exposure footprints.**

![Rakiza Structural Bridge and Exposure Chart](chart.png)

## Use case
Flat citation counts fail to capture structural risks inside scientific bibliographies:
- **Hidden pillars (3-Hop Structural Reach):** Papers with low in-sample direct citations (`<= 6`) sit upstream of dozens of studies across 2–3 citation hops (`(a)-[:CITES*1..3]->(b)`).
- **Interactive Impact Simulation (`--simulate`):** Beyond static betweenness centrality, Rakiza removes a paper from `graph.rl` to measure unbounded lost directed reachability pairs (`p.ablation_loss`), weakly connected component shifts, and affected downstream studies.
- **Dynamic Graph Updates (`--add-live`) & MCP Agent Integration (`mcp_server.py`):** AI agents connect over standard `stdio` MCP (`JSON-RPC 2.0`) or CLI `--json` to audit references, trace citation chains, and insert missing papers live while recomputing reachability deltas.

**Relationships modeled:** Directed citations `(:Paper)-[:CITES]->(:Paper)` where `a -[:CITES]-> b` means paper `a` cites `b`.

## How it uses Relate
- **Mode:** `single file` (`./graph.rl` and `./case.rl`)
- **Why this mode & division of responsibility:** Python/NetworkX computes specialized graph-theoretic metrics (`bridge` betweenness and unbounded `ablation_loss`), while `Relate` provides the zero-server, portable single-file graph store, node-property persistence, multi-hop Cypher traversal (`[:CITES*1..3]`), and CLI/MCP context interface (`--mode table` / `--mode json`).
- **What the graph models:**
  - **Nodes:** `(:Paper)` storing `id`, `title`, `year`, `date`, `cites`, `retracted`, `bridge`, `ablation_loss` (in `graph.rl`), and `temporal_tier` (in `case.rl`).
  - **Edges:** `(:Paper)-[:CITES]->(:Paper)` for in-corpus citations.

## Key Findings
1. **3-Hop Structural Reach vs. Unbounded Node Ablation (`graph.rl` — 306 papers, 605 unique edges):** *MR-based synthetic CT generation* (2017) has `4` direct in-sample citations yet achieves a bounded 3-hop structural reach of `68` papers. Under unbounded node-removal ablation (`*1..`), *Automated detection of COVID-19 cases using deep neural networks with X-ray images* (2020) causes `344` lost reachability pairs (`bridge = 0.0038`, `4` direct). Notably, *Generalist foundation models from a multimodal dataset for 3D computed tomography* (2026, `bridge = 0.0018`) breaks more reachability pairs (`167`) than a 2021 review (`bridge = 0.0019`, `155` lost pairs) because the review has more redundant alternative paths.
2. **Multi-Regime Sample Sensitivity (`sensitivity.py`):** Testing `Top-20/yr`, `Top-15/yr` (`n=192`, `8/10` Top-10 overlap), `Top-10/yr`, and 5 random 70% subsamples confirms strong rank stability across sample perturbations (`sensitivity.json`).
3. **Retraction Exposure Footprint (`case.rl` — Root `W4224073284`):** Tracks `372` citing papers (`373` nodes, `403` edges, `31` between citers) of retracted review *"U-Net-Based Medical Image Segmentation"* (retracted Oct 18, 2023), segmented into five tiers stored on nodes: `POST_12M_PLUS` (`142`), `PRE_NOTICE` (`77`), `LAG_0_6M` (`69`), `POST_6_12M` (`53`), and `AMBIGUOUS_DATE` (`31`, `-01-01` placeholder or `year=0`). Manual full-text audit of *Ling et al., Plant Methods 2023* (`10.1186/s13007-023-01096-w`, received May 2023) confirmed background-only mention and editorial lag.

## Setup and run
- **Prerequisites:** Relate CLI (`v1.0.2+`) and Python 3.10+ (zero external Python packages needed for `ask.py`, `audit.py`, `sensitivity.py`, `mcp_server.py`, and `test_rakiza.py`).

```bash
git clone https://github.com/ii8ll8iik-crypto/rakiza.git
cd rakiza

# 1. Run automated unit & MCP resilience tests (works with or without Relate CLI)
python3 -m unittest -v test_rakiza.py

# 2. Run all 5 structural, ablation, and temporal tables
python3 ask.py

# 3. Agent & researcher contextual audit with citation chains
python3 audit.py W4224073284 10.1186/s13007-023-01096-w --json

# 4. Interactive node-removal impact simulation
python3 audit.py W3009235851 --simulate

# 5. Multi-regime sample sensitivity verification
python3 sensitivity.py

# 6. Standard stdio MCP server for AI agents
python3 mcp_server.py
```

## Where the data lives
- `./graph.rl` — Persistent single-file Relate store for the medical-imaging AI corpus (`306` papers, `605` citations).
- `./case.rl` — Persistent single-file Relate store for retracted root `W4224073284` (`373` nodes, `403` citations).
- `./works.json`, `./bridge.json`, `./ablation.json`, `./sensitivity.json`, `./case.json` — Raw and intermediate snapshots.

## Methodological Limitations
1. **Subgraph boundary & year coverage:** `graph.rl` selects up to 25 top-cited works per year in OpenAlex (`n=306`; `2014` has `12` available papers and `2015` has `19`, while `2016–2026` have `25` each).
2. **Bounded 3-Hop Reach vs. Unbounded Ablation:** `structural_reach_3hop` counts citing works within `<=3` hops (`[:CITES*1..3]`), whereas `ablation_lost_reachability_pairs` evaluates unbounded transitive reachability across `graph.rl`. Neither replaces full-text inspection for experimental research dependence.
3. **Dynamic live update scope:** `--add-live` inserts the missing work into `graph.rl`, links in-sample references and snapshot citers (`works.json`), and updates `ablation_loss`, while leaving `bridge` at `0.0` and `case.rl` unmodified.
4. **Indexed dates:** `case.rl` classifies works using OpenAlex `publication_date` (isolating `-01-01` placeholders into `AMBIGUOUS_DATE`), as manuscript submission dates are not uniformly exposed in bulk metadata.
