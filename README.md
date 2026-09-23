# ⚖️ KonformAI — Agentic EU AI Act & BaFin Compliance Classifier

[![CI Pipeline](https://github.com/KonformAI/konformai/actions/workflows/ci.yml/badge.svg)](https://github.com/KonformAI/konformai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![LangGraph](https://img.shields.io/badge/Agents-LangGraph-orange.svg)](https://langchain-ai.github.io/langgraph/)

**KonformAI** is a production-grade multi-agent compliance evaluation system engineered for compliance officers and founders at German financial institutions, banks, and fintechs. It evaluates AI system architectures against the **EU Artificial Intelligence Act (Regulation (EU) 2024/1689)** and cross-references German banking regulations (**BaFin Supervisory Standards, MaRisk AT 4.3.2, KWG § 25a, and WpHG**).

---

## 📑 Final Deliverables Checklist (Spec Section 13)

- [x] **UI functional (Streamlit):** 4-screen interactive dashboard (Intake, Human Review, KB Management, Observability).
- [x] **FastAPI backend with secure handling:** Dependency injection, token validation, rate-limiting, and Alembic migrations.
- [x] **LangGraph multi-agent orchestrator with conditional routing:** Dynamic conditional edges, Article 5 hard override, critic retry loop, and HITL gates.
- [x] **At least 2 external tool/API integrations:** EUR-Lex CELLAR SPARQL endpoint, Discord Webhook notifier, Microsoft Presidio, and BaFin institution registry.
- [x] **LangSmith + OpenTelemetry observability:** Context window tracking, per-call token accounting, daily token budget, and durable PostgreSQL audit trail.
- [x] **Clean GitHub repo structure:** Pinned requirements, Dockerfile, docker-compose, CI workflow, and MIT License.
- [ ] **Demo video link:** [Watch KonformAI Demo Walkthrough](https://drive.google.com/file/d/placeholder_demo_video/view?usp=sharing) *(Placeholder: Update after recording)*
- [x] **Docker Hub image link:** `docker pull your-dockerhub-username/konformai:latest`
- [ ] **All shared Google Drive assets set to "Anyone with the link" before submission.**

---

## 🏛️ System Architecture

```text
[ Compliance Officer ]
        │
        ▼
[ Streamlit UI (:8501) ] ──▶ [ FastAPI Backend (:8000) ]
                                    │
    ┌───────────────────────────────┴───────────────────────────────┐
    ▼                                                               ▼
[ Ingestion & Presidio PII ]                          [ LangGraph Multi-Agent Engine ]
    │                                                               │
    ├─ Multi-Provider LLM Router (Groq / Gemini / OpenRouter)       ├─ 1. Intake Agent
    ├─ EUR-Lex & BaFin Tool Lookups                                 ├─ 2. Injection Sanitizer (Hard Halt on prompt attack)
    ├─ Hybrid RAG (PGVector / SQLite + BM25 Lexical)                ├─ 3. Presidio PII Scan Agent
    └─ LangSmith & OpenTelemetry Observability                      ├─ 4. EU AI Act Classifier Agent
                                                                    ├─ 5. BaFin Supervisory Agent
                                                                    ├─ 6. Translation Agent (with legal disclaimers)
                                                                    ├─ 7. Conflict Resolution Agent
                                                                    ├─ 8. Gap Assessment Agent
                                                                    ├─ 9. Critic / QA Verification Agent
                                                                    ├─ 10. Report Drafting Agent
                                                                    └─ 11. Human-in-the-Loop Approval Gate
                                                                                    │
                                                                                    ▼
                                                                    [ Verified Compliance Report ]
```

---

## 🧠 Core Architectural Principles

1. **Non-Linear LangGraph State Machine:** Dynamic routing with conditional edges, cycle loops, and feedback revisions — never a fixed linear pipeline.
2. **Article 5 Hard Override Rule:** If an Article 5 prohibited practice (social scoring, subliminal manipulation, predictive criminal profiling) is identified, the graph immediately bypasses gap assessment and routes directly to the human review gate.
3. **Critic/QA Agent with Circuit Breaker:** Verifies every statutory citation against authentic retrieved passage IDs. Enforces `MAX_CRITIC_RETRIES` (default 2) before escalating to human review.
4. **Multilingual Hybrid RAG:**
   - Dense semantic vector search via **PGVector** and **BAAI/bge-m3** (multilingual sentence embeddings).
   - Separate **BM25 lexical indexes** maintained per language (`bm25_index_en`, `bm25_index_de`).
   - Fused through LangChain's `EnsembleRetriever` (40% BM25, 60% dense vector weight).
5. **Multi-Provider LLM Router with Fallbacks:**
   - Per-agent primary model and two fallbacks defined in `.env` in `provider:model` syntax.
   - Supported providers: **Groq**, **Google Gemini**, and **OpenRouter**.
   - Automatic failover upon rate limits (429), timeouts, or API errors.
   - `GLOBAL_DRY_RUN` switch enables zero-token testing with deterministic stubs.
6. **Defense in Depth & Privacy:**
   - Microsoft Presidio scans and redacts PII before any uploaded document is indexed.
   - Regex pre-filter and semantic LLM defense intercept prompt injection attacks.
7. **Human-in-the-Loop Gate:** All critical determinations and exports require explicit approval, logged to PostgreSQL.

---

## 📚 Knowledge Base Structure & Ingestion

The regulatory knowledge base is organized under `knowledge_base/` with separated domains:

```
knowledge_base/
├── eu_ai_act/       # Regulation (EU) 2024/1689 (CELEX 32024R1689) [English]
├── bafin/           # BaFin BDAI Principles (2021) [EN], MaRisk AT 4.3.2 [DE/EN], AI Guidance 2026 [DE]
├── wphg_kwg/        # German Federal Statutes: KWG § 25a, WpHG § 63, 80 [German original]
└── uploaded/        # User-uploaded internal bank policies and controls (git-ignored)
```

### Ingesting the Knowledge Base
Run the ingestion script to parse legal boundaries (Article / § headers), populate the PGVector store, and build language-specific BM25 indexes:

```bash
python scripts/ingest_kb.py
```

### Live UI Uploads
In the Streamlit UI (**Screen 3: Regulatory Knowledge Base**), compliance officers can upload internal bank control documents (`.txt`, `.pdf`, `.docx`). The file is automatically checked for prompt injection and redacted by Presidio before being indexed into the active retrieval pool.

---

## 🚀 Quickstart & Local Setup

### 1. Prerequisites
- Python 3.11+
- Docker & Docker Compose
- (Optional) API Keys for Groq, Gemini, or OpenRouter. If no keys are available, set `GLOBAL_DRY_RUN=true`.

### 2. Environment Configuration (`.env`)

Create your local `.env` from the provided `.env.example`:

```bash
cp .env.example .env
```

#### Key Environment Variables Explained:

| Variable Group | Variable Name | Required? | Details & Guidance |
| :--- | :--- | :--- | :--- |
| **Execution Mode** | `GLOBAL_DRY_RUN` | **Yes** | Set to `false` for live real-world LLM calls, or `true` for instant zero-cost deterministic mock runs (perfect for offline testing and fast UI demos). |
| **LLM Providers** | `GROQ_API_KEY` | Optional* | Fast inference API key from [console.groq.com](https://console.groq.com). |
| | `GOOGLE_API_KEY` | Optional* | Gemini API key from [aistudio.google.com](https://aistudio.google.com). Supports `gemini-3.6-flash`. |
| | `OPENROUTER_KEY` | Optional* | OpenRouter gateway key from [openrouter.ai](https://openrouter.ai). |
| **LLM Router Chains** | `ROUTER_*_MODELS` | Defaulted | Fallback cascades per agent, e.g. `groq:llama-3.3-70b-versatile,gemini:gemini-3.6-flash,openrouter:meta-llama/llama-3.3-70b-instruct`. |
| **Observability** | `LANGCHAIN_TRACING_V2` | Optional | Set `true` to trace agent execution graphs. |
| | `LANGCHAIN_API_KEY` | Optional | Free personal API key from [smith.langchain.com](https://smith.langchain.com). *If left empty, tracing auto-disables to prevent 401 warnings.* |
| | `OTEL_EXPORTER_OTLP_ENDPOINT`| Optional | Leave blank unless feeding an OpenTelemetry collector (Jaeger, Grafana Tempo). |
| **Database** | `POSTGRES_SERVER`, etc. | Optional | PostgreSQL 16 + PGVector connection settings. *If PostgreSQL is not running, KonformAI automatically falls back to local SQLite (`konformai.db`).* |
| **Integrations** | `DISCORD_WEBHOOK_URL` | Optional | Incoming webhook URL for security alerts (Article 5 prompt injections, critic circuit-breaker escalations). |

*\* Note: At least one LLM key is needed when `GLOBAL_DRY_RUN=false`.*

---

### 3. Step-by-Step Usage Guide

#### Option A: Running with Docker Compose (Recommended for Staging/Evaluators)

1. Ensure Docker Desktop is running.
2. Build and start all multi-container services in detached mode:
   ```bash
   docker compose up --build -d
   ```
3. Access the endpoints:
   - **Streamlit Interactive UI:** [http://localhost:8501](http://localhost:8501)
   - **FastAPI OpenAPI Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **PostgreSQL Database:** `localhost:5432`

To tear down the containers:
```bash
docker compose down -v
```

---

#### Option B: Running Locally (Native Python)

##### Step 1: Set Up Python Virtual Environment
```bash
# Windows PowerShell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

##### Step 2: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements-dev.txt
```

##### Step 3: Initialize Database and Knowledge Base
```bash
# Parse statutes, generate chunks, and populate vector/BM25 indexes
python scripts/ingest_kb.py

# (Optional) Seed the 5 pre-built financial sector demonstration cases
python scripts/seed_demo_data.py
```

##### Step 4: Launch the Services (2 Terminals)

**Terminal 1 — FastAPI Backend:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Streamlit Frontend:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
streamlit run frontend/streamlit_app.py --server.port 8501
```

---

### 4. Interactive Dashboard Walkthrough

Once loaded at `http://localhost:8501`:

1. **Screen 1: System Intake & Classification**
   - Choose one of the 5 pre-loaded banking demos (e.g., *Credit Scoring Engine*, *Algorithmic Trading Bot*, *Biometric Authentication*) or input a custom system description.
   - Optionally attach company internal policy or architecture files.
   - Click **Run Assessment** to initiate the LangGraph agent pipeline.
2. **Screen 2: Human-in-the-Loop Review Gate**
   - Inspect the classified risk tier (Prohibited, High, Limited, Minimal).
   - Review cited EU AI Act Articles & Annexes alongside cross-referenced BaFin supervisory requirements.
   - Examine identified control gaps and remediation advice.
   - Sign off as Compliance Officer: **Approve Report**, **Request Agent Revision**, or **Reject**.
3. **Screen 3: Knowledge Base Management**
   - Upload new regulatory circulars or internal controls. Documents pass through automated Presidio PII sanitization before vector indexing.
4. **Screen 4: Observability & Audit Trail**
   - Inspect immutable PostgreSQL audit logs, token budgets, latency metrics, and LangSmith execution traces.

---

## 🧪 Testing & Verification

Run the complete automated pytest suite in dry-run mode (requires zero API keys):

```bash
GLOBAL_DRY_RUN=true pytest -v tests/
```

Run static analysis and linting:
```bash
ruff check .
```

---

## 🐳 Docker Hub Publishing

To build and push your container image:

```bash
# 1. Login to Docker Hub
docker login

# 2. Build multi-stage production image
docker build -t your-dockerhub-username/konformai:latest .

# 3. Push image to registry
docker push your-dockerhub-username/konformai:latest
```

---

## ⚖️ Legal & Statutory Disclaimers

> [!IMPORTANT]
> **Not Legal Advice:** KonformAI is an automated agentic compliance-support tool and does not provide formal legal advice. Final regulatory classifications and supervisory filings must be reviewed and signed off by qualified legal counsel.

> [!NOTE]
> **German Translation Authority:** In accordance with German administrative law and BaFin supervisory practice, all English translations of German statutory texts (KWG, WpHG, MaRisk) are provided for information and convenience only. The German original text is the sole legally binding authority in all respects.
