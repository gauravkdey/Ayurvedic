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

def _provider():
    """gemini (free tier) if GEMINI_API_KEY is set, else anthropic if ANTHROPIC_API_KEY is set, else None."""
    want = (os.getenv("LLM_PROVIDER") or "").lower()
    if want == "gemini" and os.getenv("GEMINI_API_KEY"): return "gemini"
    if want == "anthropic" and os.getenv("ANTHROPIC_API_KEY"): return "anthropic"
    if os.getenv("GEMINI_API_KEY"): return "gemini"
    if os.getenv("ANTHROPIC_API_KEY"): return "anthropic"
    return None

def _gemini(model, user):
    import requests
    cfg = {"maxOutputTokens": 2000, "responseMimeType": "application/json"}
    if not model.startswith("gemini-3"):      # Gemini 3 works best at its default temperature
        cfg["temperature"] = 0
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"},
        json={"systemInstruction": {"parts": [{"text": RULES}]},
              "contents": [{"role": "user", "parts": [{"text": user}]}], "generationConfig": cfg},
        timeout=15)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def gemini_models():
    first = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    return [first] + [m for m in ("gemini-flash-latest", "gemini-3.5-flash", "gemini-3.5-flash-lite") if m != first]

def _call_llm(provider, user):
    if provider == "gemini":
        last = None
        for m in gemini_models():            # overloaded (503), busy (429) or retired (404)? try the next model
            try:
                return _gemini(m, user)
            except Exception as e:
                if any(c in str(e) for c in ("400", "401", "403")): raise   # key problem: another model will not help
                last = e
        raise last
    import anthropic
    msg = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"]).messages.create(
        model=os.getenv("LLM_MODEL", "claude-sonnet-5-5"), max_tokens=500, temperature=0,
        system=RULES, messages=[{"role": "user", "content": user}])
    return msg.content[0].text

def agent2(query, cands):
    top = cands[0]; facts = facts_for(top)
    fallback = {"formulation": top["medicine"], "rationale": template(top), "cited": [3], "flag": None}
    provider = _provider()
    if not provider: return {**fallback, "flag": "template mode (no API key)", "facts": facts}
    try:
        ctx = "\n".join(f"[{i+1}] {f}" for i, f in enumerate(facts))
        text = _call_llm(provider, f"Symptoms: {query}\nFacts:\n{ctx}")
        R = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        # grounding check: formulation must be the retrieved one, citations must exist,
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
