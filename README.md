# AyurGraph (Streamlit + Neo4j + Claude)

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in your AuraDB credentials (and `ANTHROPIC_API_KEY` for Agent 2; leave blank for template mode).
3. `streamlit run app.py`
4. **Data Review** → set `verified_by_doctor` to Yes for rows the BAMS doctor confirmed → *Load verified rows into Neo4j*.
5. **Consult** → try "cough with phlegm, loss of appetite".

Rules kept from the synopsis: Agent 1 and 3 are deterministic Cypher; only Agent 2 calls an LLM and sees numbered KG facts only; its output is rejected if it names an unknown formulation or bad citation; doses are never generated; only reviewer-approved notices create BanRecords.
To extend toward 20-30 conditions, add rows from the NAMASTE portal or AFI to the CSV; they stay unloaded until verified.
