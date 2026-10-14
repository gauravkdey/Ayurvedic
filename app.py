import pandas as pd, streamlit as st
import kg, agents

st.set_page_config(page_title="AyurGraph", page_icon="ðŸŒ¿", layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Plus Jakarta Sans',system-ui,sans-serif}
.stApp{background:#F6F7F4;color:#17201B}
[data-testid=stSidebar]{background:#143e2e}[data-testid=stSidebar] *{color:#E8EFEA!important}
.stButton>button,.stFormSubmitButton>button{background:#1F5A43;color:#fff;border:0;border-radius:10px;min-height:44px;font-weight:600}
[data-testid=stVerticalBlockBorderWrapper]{background:#fff;border-radius:14px}
.b{display:inline-block;padding:6px 12px;border-radius:999px;font-weight:700;font-size:13px}
.ok{background:#E3F1E8;color:#1B5E3B}.bad{background:#FBE4E1;color:#9A2A1F}
.why{border-left:4px solid #1F5A43;background:#EEF5F0;padding:12px 14px;border-radius:0 10px 10px 0;color:#17201B}
.role{display:inline-block;background:#24493C;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700}
</style>""", unsafe_allow_html=True)

try:
    kg.driver(); has_admin = kg.bootstrap_admin()
except Exception as e:
    st.error(f"Cannot reach Neo4j. Check the NEO4J settings. ({type(e).__name__})"); st.stop()

# ---------------- Login (staff only: no sign-up page exists)
if "user" not in st.session_state:
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("## ðŸŒ¿ AyurGraph")
        st.caption("Clinical decision support for registered Ayurvedic practitioners and reviewers. Sign in with the account issued by your administrator.")
        if not has_admin:
            st.warning("No administrator exists yet. Set ADMIN_USERNAME and ADMIN_PASSWORD (at least 8 characters) in your settings, then reload.")
        with st.form("login"):
            u = st.text_input("Username"); p = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in"):
                user = kg.verify_user(u, p) if u and p else None
                if user: st.session_state.user = user; st.rerun()
                else: st.error("Incorrect username or password, or the account is inactive.")
    st.stop()

me = st.session_state.user; admin = me["role"] == "admin"
pages = ["Consult", "Knowledge Explorer", "My Decisions"] if not admin else \
        ["Consult", "Knowledge Explorer", "Data Review", "Safety Review", "Logs & Evaluation", "Users"]
st.sidebar.markdown("### ðŸŒ¿ AyurGraph")
page = st.sidebar.radio("Menu", pages, label_visibility="collapsed")
st.sidebar.markdown(f"<span class='role'>{'ADMIN / REVIEWER' if admin else 'DOCTOR'}</span> &nbsp;{me['name']}", unsafe_allow_html=True)
st.sidebar.caption(f"KG Â· {sum(r['c'] for r in kg.stats())} nodes Â· {kg.rel_count()} rels")
st.sidebar.caption("Decision support only. The treating physician decides.")
if st.sidebar.button("Sign out"): del st.session_state["user"]; st.rerun()

if page == "Consult":
    st.title("Consult"); st.caption("Enter the patient's lakshana. Recommendations come only from the doctor-verified knowledge graph.")
    q = st.text_area("Symptoms (comma separated)", "", height=80, placeholder="e.g. cough with phlegm, loss of appetite")
    k = st.slider("Top-k", 1, 5, 3)
    if st.button("Get recommendation"):
        if not q.strip(): st.warning("Please enter at least one symptom.")
        else: st.session_state.res = (q, agents.pipeline(q, k))
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
                for lab, txt, col in (("Accepted", "Accept", x), ("Overridden", "Override", y)):
                    if col.button(txt, key=f"{lab}{i}"):
                        kg.log_decision(q, c["medicine"], s["safe"], lab, me["username"]); st.toast(f"{lab} and logged")

elif page == "Knowledge Explorer":
    st.title("Knowledge Explorer")
    st.dataframe(pd.DataFrame(kg.stats()).rename(columns={"l": "Node label", "c": "Count"}), hide_index=True)
    d = st.selectbox("Trace a disease", [r["n"] for r in kg.run("MATCH (d:Disease) RETURN d.name AS n ORDER BY n")])
    st.dataframe(pd.DataFrame(kg.run("""MATCH (d:Disease {name:$d})-[r]->(x) RETURN type(r) AS relation, x.name AS node
        UNION MATCH (:Disease {name:$d})-[:TREATED_BY]->(f)-[r:CONTAINS]->(h) RETURN type(r) AS relation, h.name AS node""", d=d)), hide_index=True)

elif page == "My Decisions":
    st.title("My Decisions"); st.caption("Your accepted and overridden recommendations.")
    L = pd.DataFrame([r["d"] for r in kg.decisions(me["username"])])
    st.dataframe(L, hide_index=True, use_container_width=True) if not L.empty else st.info("No decisions yet.")

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
            kg.add_notice(f, a, str(d), ref, t, me["username"]); st.rerun()
    for p in kg.pending():
        n = p["n"]
        with st.container(border=True):
            st.write(f"**{n['formulation']}** Â· {n['action']} Â· {n['date']} Â· {n['ref']}"); st.caption(n.get("text", ""))
            x, y, _ = st.columns([1, 1, 6])
            if x.button("Approve", key="a" + n["ref"]): kg.decide_notice(n["ref"], True, me["username"]); st.rerun()
            if y.button("Reject", key="r" + n["ref"]): kg.decide_notice(n["ref"], False, me["username"], "rejected by reviewer"); st.rerun()

elif page == "Logs & Evaluation":
    st.title("Logs & Evaluation")
    L = pd.DataFrame([r["d"] for r in kg.decisions()])
    if L.empty: st.info("No decisions yet.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Decisions", len(L)); c2.metric("Accepted", (L.action == "Accepted").sum()); c3.metric("Unsafe flags", (~L.safe).sum())
        st.dataframe(L, hide_index=True, use_container_width=True)
        st.download_button("Export log (CSV)", L.to_csv(index=False), "decisions.csv")

else:  # Users (admin only)
    st.title("Users"); st.caption("Only administrators create accounts. There is no public sign-up.")
    with st.form("nu", clear_on_submit=True):
        c1, c2 = st.columns(2)
        un = c1.text_input("Username"); nm = c2.text_input("Full name")
        rl = c1.selectbox("Role", ["doctor", "admin"]); pw = c2.text_input("Temporary password (min 8 characters)", type="password")
        if st.form_submit_button("Create account"):
            if un.strip() and nm.strip() and len(pw) >= 8: kg.create_user(un, nm, rl, pw); st.success(f"Account '{un.strip().lower()}' created."); st.rerun()
            else: st.error("Username, name and a password of at least 8 characters are required.")
    U = kg.list_users(); st.dataframe(pd.DataFrame(U), hide_index=True, use_container_width=True)
    sel = st.selectbox("Account to enable or disable", [u["username"] for u in U if u["username"] != me["username"]] or [None])
    if sel:
        cur = next(u["active"] for u in U if u["username"] == sel)
        if st.button("Disable account" if cur else "Enable account"): kg.set_active(sel, not cur); st.rerun()

