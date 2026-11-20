import subprocess

queries = [
    ("1. Relative Hidden Pillars: At/Below Median Direct Citations (<=2) & High Age-Adjusted 3-Hop Reach", "graph.rl", """
    MATCH (d:Paper)-[r:CITES]->(b:Paper) WHERE r.temporal_valid = true
    WITH b, count(DISTINCT d) AS direct WHERE direct <= 2
    MATCH (a:Paper)-[r2:CITES*1..3]->(b) WHERE a <> b AND ALL(rel IN r2 WHERE rel.temporal_valid = true)
    WITH b, direct, count(DISTINCT a) AS reach_3hop WHERE reach_3hop >= 15
    RETURN b.title AS paper, b.year AS year, direct, reach_3hop,
           round((reach_3hop * 100.0) / (2026 - b.year + 1)) / 100.0 AS reach_per_yr
    ORDER BY reach_per_yr DESC, reach_3hop DESC LIMIT 10
    """),
    ("2. Structural Chokepoints (Clean vs. Raw Ablation, Betweenness & PageRank)", "graph.rl", """
    MATCH (b:Paper)
    OPTIONAL MATCH (d:Paper)-[r:CITES]->(b) WHERE r.temporal_valid = true
    WITH b, count(DISTINCT d) AS direct
    OPTIONAL MATCH (a:Paper)-[r2:CITES*1..3]->(b) WHERE a <> b AND ALL(rel IN r2 WHERE rel.temporal_valid = true)
    RETURN b.title AS paper, b.year AS year, b.ablation_loss AS clean_ablation,
           b.ablation_raw AS raw_ablation, round(b.bridge*10000)/10000.0 AS bridge,
           round(b.pagerank*10000)/10000.0 AS pagerank, direct, count(DISTINCT a) AS reach_3hop
    ORDER BY b.ablation_loss DESC LIMIT 10
    """),
    ("3. Retracted Works Inside Main Corpus (graph.rl)", "graph.rl", """
    MATCH (r:Paper {retracted: true})
    OPTIONAL MATCH (a:Paper)-[e:CITES*1..3]->(r) WHERE a <> r AND ALL(rel IN e WHERE rel.temporal_valid = true)
    RETURN r.id AS id, r.title AS paper, r.year AS year, count(DISTINCT a) AS reach_3hop
    """),
    ("4. Retraction Exposure Footprint by Temporal Tier (case.rl, Notice: 2023-10-18)", "case.rl", """
    MATCH (p:Paper) WHERE p.id <> 'W4224073284'
    RETURN p.temporal_tier AS temporal_tier, count(p) AS citing_papers
    ORDER BY citing_papers DESC
    """),
    ("5. Highest-Cited Works in Retraction Exposure Network (case.rl)", "case.rl", """
    MATCH (a:Paper)-[:CITES]->(r:Paper {id:'W4224073284'})
    RETURN a.temporal_tier AS tier, a.date AS pub_date, a.title AS citing_paper, a.cites AS global_cites
    ORDER BY a.cites DESC LIMIT 10
    """),
]

for title, db, cypher in queries:
    print(f"\n=== {title} ===")
    subprocess.run(["relate", "--database", db, "--mode", "table", cypher], check=True)
