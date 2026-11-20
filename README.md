# Rakiza (ركيزة)
**Embedded Relate graph context engine & MCP server for researchers and AI agents to audit structural reach, simulate node-ablation impact, and trace retraction exposure footprints.**

![Rakiza Structural Bridge and Exposure Chart](chart.png)

## Use case
Flat citation counts fail to capture structural risks inside scientific bibliographies:
- **Hidden pillars (Structural Reach):** Papers with low in-sample direct citations (`<= 6`) sit upstream of dozens of studies across 2–3 citation hops (`[:CITES*1..3]`).
- **Interactive Impact Simulation (`--simulate`):** Beyond static betweenness centrality, Rakiza removes a paper from `graph.rl` to measure broken indirect reachability pairs (`p.ablation_loss`), connected-component shifts, and affected downstream studies.
- **Dynamic Graph Updates (`--add-live`) & MCP Agent Integration (`mcp_server.py`):** AI agents can connect over standard `stdio` MCP or CLI `--json` to audit references, trace citation chains, and insert new papers live while computing before/after graph deltas.

**Relationships modeled:** Directed citations `(:Paper)-[:CITES]->(:Paper)` where `a -[:CITES]-> b` means `a` cites `b`; downstream structural reach traverses `(a)-[:CITES*1..3]->(b)`.

## How it uses Relate
- **Mode:** `single file` (`./graph.rl` and `./case.rl`)
- **Why this mode:** Packages each citation network into a portable, zero-server knowledge capsule that judges and AI agents can clone and query immediately via `relate` (`--mode table` or `--mode json`).
- **What the graph models:**
  - **Nodes:** `(:Paper)` storing `id`, `title`, `year`, `date`, `cites`, `retracted`, `bridge` (directed betweenness), `ablation_loss` (broken reachability pairs on node removal in `graph.rl`), and `temporal_tier` (retraction timeline classification in `case.rl`).
  - **Edges:** `(:Paper)-[:CITES]->(:Paper)` for in-corpus citations.

## Key Findings
1. **Structural Reach & Node Ablation (`graph.rl` — 306 papers, 605 citations):** *MR-based synthetic CT generation* (2017) has `4` direct in-sample citations yet reaches `68` downstream works within 3 hops. Under node-removal ablation, *Automated detection of COVID-19 cases using deep neural networks with X-ray images* (2020) severs `344` indirect reachability pairs (`bridge = 0.0038`, `4` direct). Notably, *Generalist foundation models from a multimodal dataset for 3D computed tomography* (2026, `bridge = 0.0018`) breaks more paths (`167`) than a 2021 review (`bridge = 0.0019`, `155` broken pairs) because the review has more redundant alternative paths.
2. **Sample Sensitivity Check (`sensitivity.py`):** Reducing the sample by 37% from top-25/year (`n=306`) to top-15/year (`n=192`) preserves **8/10** of the top structural chokepoints.
3. **Retraction Exposure Footprint (`case.rl` — Root `W4224073284`):** Tracks `372` citing papers (`403` edges, `31` between citers) of retracted review *"U-Net-Based Medical Image Segmentation"* (retracted Oct 18, 2023), segmented into five tiers stored on nodes: `POST_12M_PLUS` (`142`, published >= 1 year after notice), `PRE_NOTICE` (`77`), `LAG_0_6M` (`69`, potential peer-review/publication lag window), `POST_6_12M` (`53`), and `AMBIGUOUS_DATE` (`31`, `-01-01` placeholder or `year=0`). Manual full-text audit of *Ling et al., Plant Methods 2023* (`10.1186/s13007-023-01096-w`, received May 2023) confirmed background-only mention and editorial lag. **Citation reach does not imply author misconduct or invalid results.**

## Setup and run
- **Prerequisites:** Relate CLI (`v1.0.2+`) and Python 3.10+ (zero external Python packages needed for `ask.py`, `audit.py`, `sensitivity.py`, and `mcp_server.py`; `pip install -r requirements.txt` only needed to rebuild graphs/charts from scratch).

```bash
git clone https://github.com/ii8ll8iik-crypto/rakiza.git
cd rakiza

# 1. Run all 5 structural, ablation, and temporal tables
python3 ask.py

# 2. Agent & researcher contextual audit with citation chains
python3 audit.py W4224073284 10.1186/s13007-023-01096-w --json

# 3. Interactive node-removal impact simulation
python3 audit.py W3009235851 --simulate

# 4. Sample sensitivity verification (Top-25/yr vs Top-15/yr)
python3 sensitivity.py

# 5. Standard stdio MCP server for AI agents
python3 mcp_server.py
```

## Where the data lives
- `./graph.rl` — Persistent single-file Relate store for the medical-imaging AI corpus (`306` papers, `605` citations, with `bridge` and `ablation_loss` node properties).
- `./case.rl` — Persistent single-file Relate store for retracted root `W4224073284` (`373` nodes, `403` citations, with `temporal_tier` node properties).
- `./works.json`, `./bridge.json`, `./ablation.json`, `./sensitivity.json`, `./case.json` — Raw and intermediate snapshots.

## Methodological Limitations
1. **Subgraph boundary:** `graph.rl` reflects top-25 cited works per year in OpenAlex (`n=306`), not all literature.
2. **Structural Reach vs. Research Dependence:** Graph paths measure citation reach; verifying whether a citing work relies experimentally on a cited paper requires full-text analysis.
3. **Indexed dates:** `case.rl` classifies works using OpenAlex `publication_date` (excluding `-01-01` placeholders into `AMBIGUOUS_DATE`), as manuscript submission dates are not uniformly exposed in bulk metadata.
