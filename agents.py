"""Agent 1 retrieval (deterministic), Agent 2 reasoning (only LLM), Agent 3 safety (deterministic)."""
import os, json, re
from kg import run

# ---------- Agent 1 (Algorithm 1 / Appendix B.2)
RETRIEVE = """
UNWIND $terms AS t
MATCH (d:Disease)-[:HAS_SYMPTOM]->(s:Lakshana) WHERE toLower(s.name) CONTAINS toLower(t)
WITH d, collect(DISTINCT s.name) AS matched
MATCH (d)-[:HAS_SYMPTOM]->(x:Lakshana) WITH d, matched, count(x) AS total
MATCH (d)-[:TREATED_BY]->(m:Formulation)
OPTIONAL MATCH (m)-[:CONTAINS]->(h:Herb) OPTIONAL MATCH (d)-[:CAUSED_BY]->(o:Dosha)
RETURN d.name AS disease, m.name AS medicine, m.dose AS dose, m.verified AS verified,
       matched, size(matched) AS matched_count, total,
       round(toFloat(size(matched))/total, 2) AS score,
       collect(DISTINCT h.name) AS herbs, collect(DISTINCT o.name) AS doshas
ORDER BY matched_count DESC, score DESC LIMIT $k"""

def agent1(text, k=3):
    terms = [t.strip().lower() for t in text.split(",") if t.strip()]
    return run(RETRIEVE, terms=terms, k=k) if terms else []

# ---------- Agent 2 (Algorithm 2): LLM sees ONLY numbered KG facts
def facts_for(c):
    return [f"{c['disease']} HAS_SYMPTOM {', '.join(c['matched'])}",
            f"{c['disease']} CAUSED_BY {' + '.join(c['doshas'])}",
            f"{c['disease']} TREATED_BY {c['medicine']}",
            f"{c['medicine']} CONTAINS {', '.join(c['herbs'])}"]

def template(c):
    return (f"{' and '.join(c['matched'])} are lakshana of {c['disease']}, an aggravation of "
            f"{' and '.join(c['doshas'])}. {c['medicine']} is the linked classical formulation [3].")

RULES = ("You assist an Ayurvedic physician. Use ONLY the numbered facts. Cite fact numbers like [3]. "
         "Never invent a formulation, ingredient or dose. If facts are insufficient reply exactly "
         '{"formulation":null,"rationale":"insufficient information","cited":[]}. '
         'Reply with JSON only: {"formulation":str,"rationale":str,"cited":[int]}')

def agent2(query, cands):
    top = cands[0]; facts = facts_for(top)
    fallback = {"formulation": top["medicine"], "rationale": template(top), "cited": [3], "flag": None}
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key: return {**fallback, "flag": "template mode (no API key)", "facts": facts}
    try:
        import anthropic
        ctx = "\n".join(f"[{i+1}] {f}" for i, f in enumerate(facts))
        msg = anthropic.Anthropic(api_key=key).messages.create(
            model=os.getenv("LLM_MODEL", "claude-sonnet-5-5"), max_tokens=500, temperature=0,
            system=RULES, messages=[{"role": "user", "content": f"Symptoms: {query}\nFacts:\n{ctx}"}])
        R = json.loads(re.search(r"\{.*\}", msg.content[0].text, re.S).group(0))
        # grounding check: formulation must be a candidate, citations must exist,
        # and no other known formulation may be named
        names = {c["medicine"] for c in cands}
        others = [n for n in names - {top["medicine"]} if n.lower() in R["rationale"].lower()]
        ok = (R.get("formulation") == top["medicine"] and all(1 <= i <= len(facts) for i in R.get("cited", []))
              and not others)
        return {**R, "flag": None, "facts": facts} if ok else {**fallback, "flag": "LLM output rejected", "facts": facts}
    except Exception as e:
        return {**fallback, "flag": f"LLM unavailable ({type(e).__name__}); template used", "facts": facts}

# ---------- Agent 3 (Algorithm 3)
def agent3(name):
    r = run("""MATCH (f:Formulation {name:$n}) OPTIONAL MATCH (f)-[:HAS_STATUS]->(b:BanRecord)
               WHERE b.status IN ['BANNED','RESTRICTED','WITHDRAWN']
               RETURN b.status AS status, b.notice_ref AS ref""", n=name)
    if r and r[0]["status"]: return {"safe": False, **r[0]}
    return {"safe": True}

def pipeline(query, k=3):
    C = agent1(query, k)
    if not C: return None
    out = []
    reasoning = agent2(query, C)
    for i, c in enumerate(C):
        s = agent3(c["medicine"])
        out.append({"c": c, "safety": s, "why": reasoning if i == 0 else {"rationale": template(c), "facts": facts_for(c), "flag": None}})
    for o in out:
        if not o["safety"]["safe"]:
            o["alt"] = next((x["c"]["medicine"] for x in out if x["safety"]["safe"]), None)
    return out
