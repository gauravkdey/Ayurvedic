import pandas as pd, streamlit as st
import kg, agents

st.set_page_config(page_title="AyurGraph", page_icon="ðŸŒ¿", layout="wide")
st.markdown("""<style>
html,body,[class*="css"]{font-family:'Plus Jakarta Sans',system-ui,sans-serif}
.stApp{background:#F6F7F4;color:#17201B}
[data-testid=stSidebar]{background:#143e2e}[data-testid=stSidebar] *{color:#E8EFEA!important}
.stButton>button{background:#1F5A43;color:#fff;border:0;border-radius:10px;min-height:44px;font-weight:600}
.b{display:inline-block;padding:6px 12px;border-radius:999px;font-weight:700;font-size:13px}
.ok{background:#E3F1E8;color:#1B5E3B}.bad{background:#FBE4E1;color:#9A2A1F}
.why{border-left:4px solid #1F5A43;background:#EEF5F0;padding:12px 14px;border-radius:0 10px 10px 0}
</style>""", unsafe_allow_html=True)

try: kg.driver()
except Exception as e:
    st.error(f"Cannot reach Neo4j. Check NEO4J_URI / USER / PASSWORD in .env. ({type(e).__name__})"); st.stop()

page = st.sidebar.radio("AyurGraph", ["Consult", "Knowledge Explorer", "Data Review", "Safety Review", "Logs & Evaluation"])
nodes = sum(r["c"] for r in kg.stats())
st.sidebar.caption(f"KG Â· {nodes} nodes Â· {kg.rel_count()} rels")
st.sidebar.caption("Decision support only. The treating physician decides.")

if page == "Consult":
    st.title("Consult"); st.caption("Enter the patient's lakshana. Recommendations come only from the doctor-verified knowledge graph.")
    q = st.text_area("Symptoms (comma separated)", "", height=80, placeholder="e.g. cough with phlegm, loss of appetite")
    k = st.slider("Top-k", 1, 5, 3)
    if st.button("Get recommendation"):
        st.session_state.res = (q, agents.pipeline(q, k))
    if "res" in st.session_state:
        q, res = st.session_state.res
        if res is None: st.warning("Insufficient information: no lakshana match. Add more symptoms.")
        for i, o in enumerate(res or []):
            c, s = o["c"], o["safety"]
            with st.container(border=True):
                a, b = st.columns([3, 2])
                a.caption(f"#{i+1} for {c['disease']}"); a.subheader(c["medicine"])
                b.markdown(f"<span class='b {'ok' if s['safe'] else 'bad'}'>{'âœ“ SAFE Â· no active advisory' if s['safe'] else 'âœ— '+s['status']+' Â· '+str(s['ref'])}</span>", unsafe_allow_html=True)
                m1, m2, m3 = st.columns(3)
                m1.metric("Match score", f"{c['matched_count']}/{c['total']} Â· {c['score']:.2f}")
                m2.metric("Dosha", ", ".join(c["doshas"]))
                m3.metric("Dose", c["dose"] if c["dose"] and c["verified"] else "Pending doctor verification")
                st.write("**Composition:** " + ", ".join(c["herbs"]))
                st.markdown(f"<div class='why'><b>Why:</b> {o['why']['rationale']}</div>", unsafe_allow_html=True)
                if o["why"].get("flag"): st.caption(o["why"]["flag"])
                if not s["safe"]: st.error(f"Safety Agent: next safe candidate is {o.get('alt') or 'none in this set'}.")
                with st.expander("Show graph path"):
                    for f in o["why"]["facts"]: st.code(f, language=None)
                x, y, _ = st.columns([1, 1, 6])
                for lab, col in (("Accepted", x), ("Overridden", y)):
                    if col.button(lab[:-2] if lab == "Accepted" else "Override", key=f"{lab}{i}"):
                        kg.log_decision(q, c["medicine"], s["safe"], lab); st.toast(f"{lab} and logged")

elif page == "Knowledge Explorer":
    st.title("Knowledge Explorer")
    st.dataframe(pd.DataFrame(kg.stats()).rename(columns={"l": "Node label", "c": "Count"}), hide_index=True)
    d = st.selectbox("Trace a disease", [r["n"] for r in kg.run("MATCH (d:Disease) RETURN d.name AS n ORDER BY n")])
    st.dataframe(pd.DataFrame(kg.run("""MATCH (d:Disease {name:$d})-[r]->(x) RETURN type(r) AS relation, x.name AS node
        UNION MATCH (:Disease {name:$d})-[:TREATED_BY]->(f)-[r:CONTAINS]->(h) RETURN type(r), h.name""", d=d)), hide_index=True)

elif page == "Data Review":
    st.title("Data Review"); st.caption("Every row is checked by a BAMS doctor before it enters the graph. Doses come only from the AFI or the doctor.")
    up = st.file_uploader("Upload CSV (NAMASTE / AFI rows)", type="csv")
    df = pd.read_csv(up if up else "data/ayurgraph_data_v1.csv", dtype=str).fillna("")
    ed = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    st.caption("Set verified_by_doctor to Yes only after the doctor confirms the row.")
    if st.button("Load verified rows into Neo4j"):
        st.success(f"Loaded {kg.load_rows(ed.to_dict('records'))} verified rows (MERGE is idempotent).")

elif page == "Safety Review":
    st.title("Safety Review"); st.caption("Notices wait here until a reviewer approves them. Only approved records reach the Safety Agent.")
    forms = [r["n"] for r in kg.run("MATCH (f:Formulation) RETURN f.name AS n ORDER BY n")]
    with st.form("n"):
        f = st.selectbox("Formulation", forms); a = st.selectbox("Action", ["BANNED", "RESTRICTED", "WITHDRAWN"])
        d = st.date_input("Notice date"); ref = st.text_input("Notice reference no."); t = st.text_area("Notice text or link")
        if st.form_submit_button("Send to review queue") and ref:
            kg.add_notice(f, a, str(d), ref, t); st.rerun()
    for p in kg.pending():
        n = p["n"]
        with st.container(border=True):
            st.write(f"**{n['formulation']}** Â· {n['action']} Â· {n['date']} Â· {n['ref']}"); st.caption(n.get("text", ""))
            x, y, _ = st.columns([1, 1, 6])
            if x.button("Approve", key="a" + n["ref"]): kg.decide_notice(n["ref"], True); st.rerun()
            if y.button("Reject", key="r" + n["ref"]): kg.decide_notice(n["ref"], False, reason="rejected by reviewer"); st.rerun()

else:
    st.title("Logs & Evaluation")
    L = pd.DataFrame([r["d"] for r in kg.decisions()])
    if L.empty: st.info("No decisions yet. Run a consult and accept or override a card.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Decisions", len(L)); c2.metric("Accepted", (L.action == "Accepted").sum()); c3.metric("Unsafe flags", (~L.safe).sum())
        st.dataframe(L, hide_index=True, use_container_width=True)
        st.download_button("Export log (CSV)", L.to_csv(index=False), "decisions.csv")

