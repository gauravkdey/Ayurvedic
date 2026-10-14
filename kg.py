"""Neo4j access, loader (Algorithm 0) and registry update (Algorithm 4)."""
import os, csv, io, datetime as dt
from dotenv import load_dotenv
from neo4j import GraphDatabase
load_dotenv()
_driver = None
DB = os.getenv("NEO4J_DATABASE", "neo4j")

def driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(os.environ["NEO4J_URI"],
                  auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))
        _driver.verify_connectivity()
    return _driver

def run(cypher, /, **p):
    with driver().session(database=DB) as s:
        return [r.data() for r in s.run(cypher, **p)]

def split(c): return [x.strip() for x in (c or "").split(";") if x.strip()]

LOAD = """
MERGE (d:Disease {name:$disease}) MERGE (m:Formulation {name:$medicine})
MERGE (d)-[:TREATED_BY]->(m)
SET m.dose=$dose, m.source=$source, m.verified=$verified
FOREACH (s IN $symptoms | MERGE (x:Lakshana {name:s}) MERGE (d)-[:HAS_SYMPTOM]->(x))
FOREACH (o IN $doshas | MERGE (y:Dosha {name:o}) MERGE (d)-[:CAUSED_BY]->(y))
FOREACH (h IN $herbs | MERGE (z:Herb {name:h}) MERGE (m)-[:CONTAINS]->(z))"""

def load_rows(rows):
    """Loads ONLY doctor-verified rows. Doses are never generated."""
    n = 0
    for r in rows:
        if str(r.get("verified_by_doctor", "")).strip().lower() not in ("yes", "true", "1"):
            continue
        run(LOAD, disease=r["disease"].strip(), medicine=r["medicine"].strip(),
            dose=(r.get("dose") or "").strip(), source=(r.get("source") or "").strip(),
            verified=True, symptoms=split(r["symptoms"]), doshas=split(r["dosha"]),
            herbs=split(r["ingredients"]))
        n += 1
    return n

def stats():
    return run("""MATCH (n) WITH labels(n)[0] AS l, count(*) AS c RETURN l, c ORDER BY l""")

def rel_count(): return run("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]

# ---- Safety Review (Algorithm 4): notice -> PENDING -> reviewer approves -> BanRecord
def add_notice(formulation, action, date, ref, text):
    run("""MERGE (n:Notice {ref:$ref}) SET n.formulation=$f, n.action=$a, n.date=$d,
           n.text=$t, n.state='PENDING'""", ref=ref, f=formulation, a=action, d=date, t=text)

def pending(): return run("MATCH (n:Notice {state:'PENDING'}) RETURN n ORDER BY n.date")

def decide_notice(ref, approve, reviewer="reviewer", reason=""):
    if approve:
        run("""MATCH (n:Notice {ref:$ref}) SET n.state='APPROVED'
               MERGE (b:BanRecord {notice_ref:n.ref}) SET b.status=n.action, b.date=n.date
               WITH n,b MATCH (f:Formulation {name:n.formulation}) MERGE (f)-[:HAS_STATUS]->(b)""", ref=ref)
    else:
        run("MATCH (n:Notice {ref:$ref}) SET n.state='REJECTED', n.reason=$r", ref=ref, r=reason)

def log_decision(q, formulation, safe, action):
    run("""CREATE (:Decision {t:$t, query:$q, formulation:$f, safe:$s, action:$a})""",
        t=dt.datetime.now().isoformat(timespec="seconds"), q=q, f=formulation, s=safe, a=action)

def decisions(): return run("MATCH (d:Decision) RETURN d ORDER BY d.t DESC LIMIT 200")
