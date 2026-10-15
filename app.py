import html, pandas as pd, streamlit as st
import kg, agents

st.set_page_config(page_title="AyurGraph", page_icon="🌿", layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500&display=swap');
html,body,[class*="css"]{font-family:'Plus Jakarta Sans',system-ui,sans-serif}
.stApp{background:#F6F7F4;color:#17201B}footer{visibility:hidden}
[data-testid=stSidebar]{background:#143e2e}[data-testid=stSidebar] *{color:#E8EFEA!important}
[data-testid=stSidebar] [role=radiogroup]{gap:4px}
[data-testid=stSidebar] [role=radiogroup] label{padding:10px 14px;border-radius:10px;width:100%}
[data-testid=stSidebar] [role=radiogroup] label>div:first-child{display:none}
[data-testid=stSidebar] [role=radiogroup] label:has(input:checked){background:#24493C;font-weight:700}
.stButton>button,.stFormSubmitButton>button{background:#1F5A43;color:#fff;border:0;border-radius:10px;min-height:44px;font-weight:600}
[data-testid=stVerticalBlockBorderWrapper]{background:#fff;border-radius:14px}
.b{display:inline-block;padding:6px 12px;border-radius:999px;font-weight:700;font-size:13px}
.ok{background:#E3F1E8;color:#1B5E3B}.bad{background:#FBE4E1;color:#9A2A1F}.warn{background:#FFF1D6;color:#7A5200}
.why{border-left:4px solid #1F5A43;background:#EEF5F0;padding:12px 14px;border-radius:0 10px 10px 0;color:#17201B}
.chip{display:inline-block;padding:5px 12px;margin:3px 6px 3px 0;border-radius:999px;font-size:13px;font-weight:600;background:#EEF5F0;color:#1F5A43;border:1px solid #DDE2DA}
.chip.l{background:#DDF5F7;color:#0F5F66}.chip.d{background:#FBE0D6;color:#8A3A1E}.chip.f{background:#EFE3D0;color:#6B4A1F}.chip.h{background:#FFEFC9;color:#7A5200}
.sec{font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#56615A;margin:14px 0 4px}
.brand{background:linear-gradient(160deg,#143e2e,#1F5A43);color:#fff;border-radius:18px;padding:40px 34px;min-height:520px}
.brand h1{color:#fff;margin:0 0 4px}.brand h3{color:#fff;font-weight:600;margin:26px 0 8px;line-height:1.3}
.brand p,.brand li{color:#CFE3D6}.brand li{margin:10px 0}.brand small{color:#9FD3B5}
.nav-label{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#9FD3B5!important;margin:6px 0 2px}
.role{display:inline-block;background:#24493C;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700}
</style>""", unsafe_allow_html=True)

try:
    kg.driver(); has_admin = kg.bootstrap_admin()
except Exception as e:
    st.error(f"Cannot reach Neo4j. Check the NEO4J settings. ({type(e).__name__})"); st.stop()

ROLE_OF = {"Doctor": "doctor", "Reviewer / Admin": "admin"}
MENU = {"doctor": ["Consult", "Knowledge Explorer"],
        "admin": ["Safety Review", "Data Review", "Logs & Evaluation", "Knowledge Explorer", "Users"]}
chip = lambda t, k="": f"<span class='chip {k}'>{html.escape(str(t))}</span>"

# ================= Sign in (role picker, as in the design) =================
if "user" not in st.session_state:
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.markdown("""<div class='brand'><h1>🌿 AyurGraph</h1><small>Clinical decision support</small>
        <h3>Classical formulations, with the reason behind every suggestion.</h3>
        <p>An explainable decision-support assistant for Ayurvedic practitioners, grounded in a doctor-verified knowledge graph.</p>
        <ul><li>Medicine, composition and dose from verified sources</li>
        <li>A visible reasoning path: lakshana → disease → dosha → formulation</li>
        <li>Every recommendation checked against approved ban and advisory notices</li></ul>
        <p style='margin-top:40px'><small>Research prototype · Dept. of CSE, Chandigarh University</small></p></div>""", unsafe_allow_html=True)
    with right:
        st.markdown("## Sign in"); st.caption("Choose your role to continue.")
        if not has_admin:
            st.warning("No administrator exists yet. Set ADMIN_USERNAME and ADMIN_PASSWORD (at least 8 characters) in your settings, then reload.")
        role = st.radio("Role", list(ROLE_OF), horizontal=True)
        with st.form("login"):
            u = st.text_input("Username (email or registration no.)"); p = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in", use_container_width=True):
                user = kg.verify_user(u, p) if u and p else None
                if not user: st.error("Incorrect username or password, or the account is inactive.")
                elif user["role"] != ROLE_OF[role]: st.error(f"This account is not a {role} account. Pick the other role.")
                else:
                    st.session_state.user = user; st.session_state.page = MENU[user["role"]][0]; st.rerun()
        st.caption("Forgot your password? Ask your administrator to reset it.")
        st.caption("Decision support only. The treating physician remains responsible for diagnosis and prescription. No patient-identifying data is stored.")
    st.stop()

# ================= Shell =================
me = st.session_state.user; role = me["role"]; admin = role == "admin"
st.sidebar.markdown("### 🌿 AyurGraph")
st.sidebar.markdown(f"<div class='nav-label'>{'Reviewer' if admin else 'Doctor'}</div>", unsafe_allow_html=True)
if st.session_state.get("page") not in MENU[role]: st.session_state.page = MENU[role][0]
page = st.sidebar.radio("Menu", MENU[role], key="page", label_visibility="collapsed")
st.sidebar.caption(f"KG v1 · {sum(r['c'] for r in kg.stats())} nodes · {kg.rel_count()} rels")
st.sidebar.markdown(f"<span class='role'>Signed in as {'Reviewer' if admin else 'Doctor'}</span><br><small>{html.escape(me['name'])}</small>", unsafe_allow_html=True)
if st.sidebar.button("Sign out"): del st.session_state["user"]; st.rerun()

# ================= DOCTOR: Consult =================
if page == "Consult":
    st.title("Consult"); st.caption("Enter the patient's lakshana. Recommendations come only from the doctor-verified knowledge graph.")
    q = st.text_area("Symptoms (comma separated)", "", height=80, placeholder="e.g. cough with phlegm, loss of appetite")
    c1, c2 = st.columns([3, 2]); k = c1.slider("Top-k", 1, 5, 3)
    c2.caption("Retrieval → Reasoning → Safety")
    if st.button("Get recommendation"):
        if not q.strip(): st.warning("Please enter at least one symptom.")
        else: st.session_state.res = (q, agents.pipeline(q, k))
    if "res" in st.session_state:
        q, res = st.session_state.res
        if res is None: st.warning("Insufficient information: no lakshana match. Add more symptoms.")
        else: st.subheader("Recommendations"); st.caption(f"{len(res)} candidate{'s' if len(res)>1 else ''} · ranked by matched symptoms")
        for i, o in enumerate(res or []):
            c, s = o["c"], o["safety"]
            with st.container(border=True):
                a, b = st.columns([3, 2])
                a.caption(f"#{i+1} · for {c['disease']}"); a.subheader(c["medicine"])
                b.markdown(f"<span class='b {'ok' if s['safe'] else 'bad'}'>{'✓ SAFE · no active advisory' if s['safe'] else '✗ '+s['status']+' · '+str(s['ref'])}</span>", unsafe_allow_html=True)
                m1, m2, m3 = st.columns(3)
                m1.metric("Match score", f"{c['matched_count']}/{c['total']} · {c['score']:.2f}")
                m2.metric("Dosha", ", ".join(c["doshas"]))
                m3.metric("Dose", c["dose"] if c["dose"] and c["verified"] else "Pending doctor verification")
                st.markdown("<div class='sec'>Composition</div>" + "".join(chip(h, "h") for h in c["herbs"]), unsafe_allow_html=True)
                st.markdown(f"<div class='why'><b>Why this recommendation:</b> {html.escape(o['why']['rationale'])}</div>", unsafe_allow_html=True)
                if o["why"].get("flag"): st.caption(o["why"]["flag"])
                if not s["safe"]: st.error(f"Safety Agent: next safe candidate is {o.get('alt') or 'none in this set'}.")
                with st.expander("Show graph path"):
                    for f in o["why"]["facts"]: st.code(f, language=None)
                x, y, _ = st.columns([1, 1, 6])
                for lab, txt, col in (("Accepted", "Accept", x), ("Overridden", "Override", y)):
                    if col.button(txt, key=f"{lab}{i}"):
                        kg.log_decision(q, c["medicine"], s["safe"], lab, me["username"]); st.toast(f"{lab} and logged")

# ================= BOTH: Knowledge Explorer =================
elif page == "Knowledge Explorer":
    st.title("Knowledge Explorer"); st.caption("Browse the verified graph: every disease, its lakshana, dosha, formulation and herbs.")
    cnt = {r["l"]: r["c"] for r in kg.stats()}
    cols = st.columns(5)
    for col, l in zip(cols, ["Disease", "Lakshana", "Dosha", "Formulation", "Herb"]): col.metric(l, cnt.get(l, 0))
    sq = st.text_input("Search disease, herb or formulation", placeholder="e.g. Pippali")
    names = kg.search_diseases(sq)
    if not names: st.info("No match in the graph.")
    else:
        l, r = st.columns([1, 2.4], gap="large")
        sel = l.radio("Diseases", names)
        d = kg.disease_detail(sel)
        with r.container(border=True):
            st.subheader(sel); st.caption("1-hop and 2-hop relationships")
            st.markdown("<div class='sec'>Lakshana · HAS_SYMPTOM</div>" + "".join(chip(x, "l") for x in d["symptoms"]), unsafe_allow_html=True)
            st.markdown("<div class='sec'>Dosha · CAUSED_BY</div>" + "".join(chip(x, "d") for x in d["doshas"]), unsafe_allow_html=True)
            if d["formulation"]:
                s = agents.agent3(d["formulation"])
                badge = f"<span class='b {'ok' if s['safe'] else 'bad'}'>{'SAFE' if s['safe'] else s['status']}</span>"
                dose = d["dose"] if d["dose"] and d["verified"] else "doctor to verify"
                st.markdown(f"<div class='sec'>Formulation · TREATED_BY</div>{chip(d['formulation'], 'f')} {badge}<br><small>Dose: {html.escape(dose)} · Source: {html.escape(d['source'] or '-')}</small>", unsafe_allow_html=True)
            st.markdown(f"<div class='sec'>Herbs · CONTAINS ({len(d['herbs'])})</div>" + "".join(chip(x, "h") for x in d["herbs"]), unsafe_allow_html=True)

# ================= REVIEWER: Safety Review =================
elif page == "Safety Review":
    st.title("Safety Review"); st.caption("New CDSCO / Ministry of Ayush notices wait here until a reviewer approves them. Only approved records reach the Safety Agent.")
    forms = [r["n"] for r in kg.run("MATCH (f:Formulation) RETURN f.name AS n ORDER BY n")]
    pend = kg.pending()
    st.subheader(f"Pending review · {len(pend)} waiting")
    if not pend: st.info("No notices waiting.")
    for p in pend:
        n = p["n"]
        with st.container(border=True):
            h1, h2 = st.columns([3, 1]); h1.markdown(f"**{n['formulation']}**"); h2.markdown(f"<span class='b warn'>{n['action']}</span>", unsafe_allow_html=True)
            st.caption(f"Ref: {n['ref']} · Date: {n['date']} · Added by: {n.get('added_by') or 'system'}")
            if n.get("text"): st.write(n["text"])
            st.caption("Effect if approved: the Safety Agent will flag this formulation and suggest the next safe candidate.")
            x, y, _ = st.columns([1, 1, 6])
            if x.button("Approve", key="a" + n["ref"]): kg.decide_notice(n["ref"], True, me["username"]); st.rerun()
            if y.button("Reject", key="r" + n["ref"]): kg.decide_notice(n["ref"], False, me["username"], "rejected by reviewer"); st.rerun()
    with st.expander("Add a notice", expanded=not pend):
        with st.form("n", clear_on_submit=True):
            f = st.selectbox("Formulation", forms); a = st.selectbox("Action", ["BANNED", "RESTRICTED", "WITHDRAWN"])
            d = st.date_input("Notice date"); ref = st.text_input("Notice reference no."); t = st.text_area("Notice text or link")
            if st.form_submit_button("Send to review queue") and ref:
                kg.add_notice(f, a, str(d), ref, t, me["username"]); st.rerun()
    st.subheader("Active ban / advisory registry")
    R = kg.registry(); st.dataframe(pd.DataFrame(R), hide_index=True, use_container_width=True) if R else st.caption("Empty. Every formulation currently reads as safe.")

# ================= REVIEWER: Data Review =================
elif page == "Data Review":
    st.title("Data Review"); st.caption("Every new row is checked by a BAMS doctor before it enters the knowledge graph. Doses come only from the AFI or the doctor.")
    up = st.file_uploader("Upload CSV (NAMASTE / AFI rows)", type="csv")
    df = pd.read_csv(up if up else "data/ayurgraph_data_v1.csv", dtype=str).fillna("")
    yes = df["verified_by_doctor"].str.strip().str.lower().isin(["yes", "true", "1"]).sum()
    m1, m2, m3 = st.columns(3); m1.metric("Awaiting doctor", len(df) - yes); m2.metric("Verified, ready to load", yes); m3.metric("Target for evaluation", "20–30")
    ed = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    st.caption("Set verified_by_doctor to Yes only after the doctor confirms the row.")
    if st.button("Load verified rows into Neo4j"):
        st.success(f"Loaded {kg.load_rows(ed.to_dict('records'))} verified rows (MERGE is idempotent).")

# ================= REVIEWER: Logs & Evaluation =================
elif page == "Logs & Evaluation":
    st.title("Logs & Evaluation"); st.caption("Every recommendation and doctor decision is logged. Blind ratings feed the research results.")
    L = pd.DataFrame([r["d"] for r in kg.decisions()])
    acc = int((L.action == "Accepted").sum()) if not L.empty else 0
    c = st.columns(4); c[0].metric("Queries", len(L)); c[1].metric("Accepted", acc); c[2].metric("Overridden", len(L) - acc); c[3].metric("Safety flags", int((~L.safe).sum()) if not L.empty else 0)
    st.subheader("Decision log")
    if L.empty: st.info("No decisions yet.")
    else:
        st.dataframe(L.rename(columns={"t": "Time", "query": "Symptoms", "formulation": "Top recommendation", "safe": "Safe", "action": "Doctor", "user": "User"}), hide_index=True, use_container_width=True)
        st.download_button("Export CSV", L.to_csv(index=False), "decisions.csv")
    st.subheader("Evaluation: AyurGraph vs plain LLM")
    st.caption("Blind physician ratings are collected outside the app. Enter the means here once the study is done.")
    st.dataframe(pd.DataFrame({"Metric": ["Correctness (1-5)", "Reason clarity (1-5)", "Safety (1-5)", "Hallucination rate"], "AyurGraph": ["-"] * 4, "Plain LLM": ["-"] * 4}), hide_index=True)

# ================= REVIEWER: Users =================
else:
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
