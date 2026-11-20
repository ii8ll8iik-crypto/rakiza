import subprocess

queries = [
    ("1. Hidden Pillars: Low Direct Citations (<=6) vs High 3-Hop Structural Reach (graph.rl)", "graph.rl", """
    MATCH (d:Paper)-[:CITES]->(b:Paper)
    WITH b, count(DISTINCT d) AS direct WHERE direct <= 6
    MATCH (a:Paper)-[:CITES*1..3]->(b) WHERE a <> b
    RETURN b.title AS paper, b.year AS year, direct, count(DISTINCT a) AS structural_reach_3hop
    ORDER BY structural_reach_3hop DESC LIMIT 10
    """),
    ("2. Structural Bridges vs Node Ablation Chokepoints (graph.rl)", "graph.rl", """
    MATCH (d:Paper)-[:CITES]->(b:Paper)
    WITH b, count(DISTINCT d) AS direct
    MATCH (a:Paper)-[:CITES*1..3]->(b) WHERE a <> b
    RETURN b.title AS paper, b.year AS year, round(b.bridge*10000)/10000.0 AS bridge,
           b.ablation_loss AS broken_pairs_on_removal, direct, count(DISTINCT a) AS reach_3hop
    ORDER BY b.ablation_loss DESC LIMIT 10
    """),
    ("3. Retracted Works Inside Main Corpus (graph.rl)", "graph.rl", """
    MATCH (r:Paper {retracted: true})
    OPTIONAL MATCH (a:Paper)-[:CITES*1..3]->(r) WHERE a <> r
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
