# AyurGraph

**An Explainable Agentic Knowledge Graph Framework for Ayurvedic Medicine Recommendation**

AyurGraph is a clinical decision-support tool for Ayurvedic practitioners. A doctor types a patient's symptoms (*lakshana*); the system returns ranked classical formulations with their composition, dose, a clinician-readable reason, and a regulatory safety status. Every answer is traced to an explicit path in a doctor-verified **Neo4j knowledge graph**, and that path is the explanation.

> **Decision support only.** The treating physician is responsible for diagnosis and prescription. This project is a university prototype and is not a medical device.

Project synopsis submitted for the B.E. (Hons.) in Computer Science and Engineering (Big Data Analytics), Chandigarh University, October 2026.

**Team:** Kritika Dua (23BDA70142), Gouranga (23BDA70125), Chirag (23BDA70140)
**Supervisor:** Ratish Kumar (E14394)

---

## Why this project

Information about an Ayurvedic formulation is spread across classical texts, the Ayurvedic Formulary of India (AFI), and government notices. A practitioner has to cross-check several sources by hand. Plain LLMs can answer instantly, but without grounding they can invent formulations, doses or safety claims. AyurGraph keeps the LLM away from fact selection: facts come from the graph, and the LLM only phrases them.

## Features

- **Consult:** enter symptoms, get ranked formulations with match score, dosha, composition, dose, reason and safety badge. Doctors can Accept or Override each card.
- **Explainable:** every card has a graph path (Lakshana → Disease → Dosha → Formulation → Herb).
- **Three cooperating agents** (see below).
- **Data Review:** a doctor marks each row as verified before it is loaded into Neo4j. Unverified rows never enter the graph.
- **Safety Review:** new ban or advisory notices wait in a queue until a human reviewer approves them. Only approved notices reach the Safety Agent.
- **Logs & Evaluation:** every accept/override is stored in Neo4j and can be exported as CSV for the physician's blind rating.
- **Knowledge Explorer:** inspect node counts and trace any disease through the graph.

## Architecture

```
Doctor types symptoms
        |
Agent 1  Retrieval  <-->  Neo4j knowledge graph
        |
Agent 2  Reasoning  <-->  LLM API (numbered KG facts only)
        |
Agent 3  Safety     <-->  Ban registry (approved notices)
        |
Answer card (Accept / Override)  -->  Logs & Evaluation
```

| Agent | Type | Role |
|---|---|---|
| **Agent 1: Retrieval** | Deterministic (Cypher) | Matches the symptoms to Lakshana nodes and ranks diseases by number of matched symptoms, then by `score = matched / total symptoms`. |
| **Agent 2: Reasoning** | Only LLM component | Writes the "Why" using only numbered facts from the retrieved sub-graph. A grounding check rejects the output if it names an unknown formulation or cites a missing fact, and falls back to a template rationale. |
| **Agent 3: Safety** | Deterministic (Cypher) | Looks up each formulation's `BanRecord` (BANNED / RESTRICTED / WITHDRAWN) and proposes the next safe candidate when one is flagged. |

## Knowledge graph schema

| Node | Properties |
|---|---|
| `Disease` | name |
| `Lakshana` | name (symptom) |
| `Dosha` | name |
| `Formulation` | name, dose, source, verified |
| `Herb` | name |
| `BanRecord` | status, notice_ref, date |
| `Notice`, `Decision` | review-queue and decision-log nodes used by the app |

Relationships: `HAS_SYMPTOM`, `CAUSED_BY`, `TREATED_BY`, `CONTAINS`, `HAS_STATUS`.

The pilot graph covers five conditions (Amlapitta, Kasa, Vibandha, Ajirna, Pratishyaya) and loads as **51 nodes and 67 relationships**.

## Project structure

```
ayurgraph_app/
├── app.py                  # Streamlit interface (5 screens)
├── agents.py               # Agent 1 retrieval, Agent 2 reasoning, Agent 3 safety
├── kg.py                   # Neo4j connection, loader, safety-review workflow, logs
├── data/
│   └── ayurgraph_data_v1.csv   # Pilot dataset (5 conditions)
├── .streamlit/config.toml  # Light theme
├── .env.example            # Template for your private settings
├── requirements.txt
└── README.md
```

## Access and roles

AyurGraph is for **registered practitioners and reviewers only**. There is no public sign-up page.

| Role | Can do |
|---|---|
| **Doctor** | Consult, Knowledge Explorer, My Decisions |
| **Admin / Reviewer** | Everything a doctor can, plus Data Review, Safety Review, Logs & Evaluation and Users (create or disable accounts) |

The first administrator is created automatically on first run from `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env` (or the Streamlit Secrets). Sign in as that admin, then create doctor accounts in **Users**. Passwords are stored as salted PBKDF2 hashes in Neo4j, never in plain text. Change the admin password settings after the first login and keep them private.

## Getting started

### 1. Prerequisites
- Python 3.9 or newer
- A free **Neo4j AuraDB** instance
- (Optional) an **Anthropic API key** for the Agent 2 LLM

### 2. Create the Neo4j database
1. Sign in at https://console.neo4j.io and click **Create instance**, then choose **AuraDB Free**.
2. **Download the credentials file.** The password is shown only once.
3. Wait until the instance status is **Running**.

### 3. Install
```bash
git clone https://github.com/gauravkdey/Ayurvedic.git
cd Ayurvedic
pip install -r requirements.txt
```

### 4. Configure
Copy `.env.example` to `.env` (Windows: `copy .env.example .env`) and fill it in:

```
NEO4J_URI=neo4j+s://<your-instance-id>.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=<your generated password>
NEO4J_DATABASE=neo4j
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<a strong password, min 8 characters>
ANTHROPIC_API_KEY=
LLM_MODEL=claude-sonnet-5-5
```

- Use the user and database values from your downloaded credentials file. On newer Aura instances they may be the instance ID instead of `neo4j`.
- Leave `ANTHROPIC_API_KEY` empty to run in **template mode** (no LLM call).
- **Never commit `.env`.** It is listed in `.gitignore`.

### 5. Run
```bash
streamlit run app.py
```
The app opens at http://localhost:8501.

### 6. Load the data
1. Open **Data Review**.
2. Set `verified_by_doctor` to **Yes** for rows a BAMS physician has confirmed.
3. Click **Load verified rows into Neo4j**. The sidebar should show the new node and relationship counts.

### 7. Try it
- **Consult:** `cough with phlegm, loss of appetite, heaviness in chest` should rank *Sitopaladi Churna* first.
- **Safety Review:** add a test notice for a formulation, approve it, and run the consult again. The card should show the new safety status.
- **Logs & Evaluation:** accept or override a card to see it recorded.

## Adding more conditions

The evaluation plan targets 20 to 30 conditions. Add rows to the CSV (or upload one in **Data Review**) using these columns:

| Column | Description |
|---|---|
| `disease` | Classical disease name with English gloss |
| `symptoms` | Lakshana separated by `;` |
| `dosha` | Aggravated dosha(s), separated by `;` |
| `medicine` | Classical formulation |
| `ingredients` | Herbs separated by `;` |
| `dose` | Standard dose from the AFI or the physician |
| `source` | e.g. AFI Part I, NAMASTE |
| `verified_by_doctor` | `Yes` / `No` |

Source data should come from the AFI, AyurKOSH and the Ministry of Ayush **NAMASTE** terminology portal. The app does not fetch data from NAMASTE automatically; rows are curated by hand and verified by a doctor before loading.

## Design rules

- **Doses are never generated.** They come only from the AFI or the physician. Until a dose is verified, the app shows "Pending doctor verification".
- **Only verified rows enter the graph.**
- **The LLM sees only retrieved facts**, uses temperature 0, and its output is rejected if it is not grounded.
- **Ban records need human approval** before the Safety Agent uses them.
- **No patient data** is collected or sent to the LLM. Use synthetic vignettes only.
- Seeded test ban records must be clearly marked as synthetic and never presented as real regulatory actions.

## Evaluation plan

AyurGraph will be compared with a plain-LLM baseline on 25 to 27 curated clinical vignettes. A practising BAMS physician blind-rates correctness, reason clarity and safety. Metrics: Hit@k, hallucination rate, safety recall, and win/tie/loss.

Target criteria: Hit@3 ≥ 0.80, higher physician ratings and a lower hallucination rate than the baseline, and safety recall of 1.0 on seeded banned cases.

## Current status

| Module | Status |
|---|---|
| Pilot dataset (5 conditions) and Neo4j graph | Done |
| Agent 1: retrieval | Implemented |
| Agent 2: LLM reasoning with grounding check | Implemented (template mode without an API key) |
| Agent 3: safety and human-approved review | Implemented |
| Streamlit interface | Implemented |
| Expansion to 20 to 30 conditions with doctor verification | In progress |
| Doses verified by a BAMS physician | Pending |
| Evaluation with BAMS physician | Planned |

## Known limitations

- Pilot scope: five conditions, one formulation each.
- Text-only input. Matching is by substring, so unusual or misspelt terms may not match.
- Basic login only: no password reset by email, no lockout after repeated failures, and no multi-factor authentication.
- Out of scope: proprietary and folk formulations, multimodal input (pulse, tongue images).

## Future work

Nidana, upashaya, prakriti and contraindications in the schema; NAMASTE terminology mapping; Hindi and Sanskrit input; LLM-assisted parsing of CDSCO notices with human approval; multi-physician evaluation.

## Tech stack

Python, Streamlit, Neo4j AuraDB (Cypher), the Neo4j Python driver, pandas, the Anthropic API.

## References

Think-on-Graph (Sun et al., 2024), Microsoft GraphRAG (Edge et al., 2024), OpenTCM (He et al., 2025), AMG-RAG (Rezaei et al., 2025), Retrieval-Augmented Generation (Lewis et al., 2020), the Ayurvedic Formulary of India, CCRAS DRAVYA, and TKDL. The full list is in the project synopsis.
