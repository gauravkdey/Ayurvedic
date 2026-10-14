"""Neo4j access, loader (Algorithm 0), registry update (Algorithm 4), staff accounts."""
import os, csv, hmac, hashlib, secrets, datetime as dt
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

def stats(): return run("MATCH (n) WITH labels(n)[0] AS l, count(*) AS c RETURN l, c ORDER BY l")
def rel_count(): return run("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]

# ---- Safety Review (Algorithm 4)
def add_notice(formulation, action, date, ref, text, by=""):
    run("""MERGE (n:Notice {ref:$ref}) SET n.formulation=$f, n.action=$a, n.date=$d,
           n.text=$t, n.state='PENDING', n.added_by=$by""", ref=ref, f=formulation, a=action, d=date, t=text, by=by)

def pending(): return run("MATCH (n:Notice {state:'PENDING'}) RETURN n ORDER BY n.date")

def decide_notice(ref, approve, by="", reason=""):
    if approve:
        run("""MATCH (n:Notice {ref:$ref}) SET n.state='APPROVED', n.decided_by=$by
               MERGE (b:BanRecord {notice_ref:n.ref}) SET b.status=n.action, b.date=n.date
               WITH n,b MATCH (f:Formulation {name:n.formulation}) MERGE (f)-[:HAS_STATUS]->(b)""", ref=ref, by=by)
    else:
        run("MATCH (n:Notice {ref:$ref}) SET n.state='REJECTED', n.reason=$r, n.decided_by=$by", ref=ref, r=reason, by=by)

def log_decision(q, formulation, safe, action, user=""):
    run("""CREATE (:Decision {t:$t, query:$q, formulation:$f, safe:$s, action:$a, user:$u})""",
        t=dt.datetime.now().isoformat(timespec="seconds"), q=q, f=formulation, s=safe, a=action, u=user)

def decisions(user=None):
    if user: return run("MATCH (d:Decision {user:$u}) RETURN d ORDER BY d.t DESC LIMIT 200", u=user)
    return run("MATCH (d:Decision) RETURN d ORDER BY d.t DESC LIMIT 200")

# ---- Staff accounts (no public sign-up: only an admin creates accounts)
def _hash(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt, hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()

def create_user(username, name, role, password):
    salt, h = _hash(password)
    run("""MERGE (u:User {username:$u}) SET u.name=$n, u.role=$r, u.salt=$s, u.hash=$h, u.active=true""",
        u=username.strip().lower(), n=name.strip(), r=role, s=salt, h=h)

def verify_user(username, password):
    rows = run("MATCH (u:User {username:$u, active:true}) RETURN u", u=username.strip().lower())
    if not rows:
        _hash(password); return None            # keeps timing similar
    u = rows[0]["u"]
    _, h = _hash(password, u["salt"])
    return {"username": u["username"], "name": u["name"], "role": u["role"]} if hmac.compare_digest(h, u["hash"]) else None

def list_users(): return run("MATCH (u:User) RETURN u.username AS username, u.name AS name, u.role AS role, u.active AS active ORDER BY role, username")
def set_active(username, active): run("MATCH (u:User {username:$u}) SET u.active=$a", u=username, a=active)

def bootstrap_admin():
    """First run only: creates the first admin from ADMIN_USERNAME / ADMIN_PASSWORD. Returns True if an admin exists."""
    if run("MATCH (u:User {role:'admin'}) RETURN count(u) AS c")[0]["c"]: return True
    u, p = os.getenv("ADMIN_USERNAME"), os.getenv("ADMIN_PASSWORD")
    if u and p and len(p) >= 8:
        create_user(u, "Administrator", "admin", p); return True
    return False
