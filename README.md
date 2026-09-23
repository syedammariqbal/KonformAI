# ⚖️ KonformAI — Agentic EU AI Act & BaFin Compliance Classifier

[![CI Pipeline](https://github.com/KonformAI/konformai/actions/workflows/ci.yml/badge.svg)](https://github.com/KonformAI/konformai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![LangGraph](https://img.shields.io/badge/Agents-LangGraph-orange.svg)](https://langchain-ai.github.io/langgraph/)

**KonformAI** is a production-grade multi-agent compliance evaluation system engineered for compliance officers and founders at German financial institutions, banks, and fintechs. It evaluates AI system architectures against the **EU Artificial Intelligence Act (Regulation (EU) 2024/1689)** and cross-references German banking regulations (**BaFin Supervisory Standards, MaRisk AT 4.3.2, KWG § 25a, and WpHG**).

---

## 📑 Final Deliverables

- [x] **UI functional (Streamlit):** 4-screen interactive dashboard (Intake, Human Review, KB Management, Observability).
- [x] **FastAPI backend with secure handling:** Dependency injection, token validation, rate-limiting, and Alembic migrations.
- [x] **LangGraph multi-agent orchestrator with conditional routing:** Dynamic conditional edges, Article 5 hard override, critic retry loop, and HITL gates.
- [x] **At least 2 external tool/API integrations:** EUR-Lex CELLAR SPARQL endpoint, Discord Webhook notifier, Microsoft Presidio, and BaFin institution registry.
- [x] **LangSmith + OpenTelemetry observability:** Context window tracking, per-call token accounting, daily token budget, and durable PostgreSQL audit trail.
- [x] **GitHub repo structure:** Pinned requirements, Dockerfile, docker-compose, CI workflow, and MIT License.

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

## 🤖 Multi-Agent Framework & Orchestration

KonformAI implements an adaptive, non-linear multi-agent orchestration architecture powered by **LangGraph**. The workflow avoids brittle, linear pipelines by leveraging directed cyclical graphs with dynamic feedback edges, confidence checkpoints, and automated revision loops.

### Agent Taxonomy & Roles

The system organizes its agents into an orchestration supervisor and specialized functional agents, combining **deterministic programmatic agents** (for strict security, verification, and boundary compliance) and **LLM-based cognitive agents** (for regulatory interpretation, synthesis, and reasoning):

| Sequence | Agent Name | Category | Execution Type | Primary Role & Responsibility |
| :--- | :--- | :--- | :--- | :--- |
| **0** | **Supervisor Orchestrator** | Orchestration | **Deterministic** | Manages the dynamic `StateGraph`, evaluates conditional edges, routes state between nodes, triggers parallel execution, and enforces human review checkpoints. |
| **1** | **Intake Agent** | Ingestion & Structuring | **LLM-Based** | Parses unstructured system descriptions and user documents into a normalized schema (`system_purpose`, `affected_persons`, `decision_autonomy_level`, `data_types_used`). |
| **2** | **Injection Sanitizer Agent** | Security Guardrail | **Deterministic + LLM Fallback** | Defends against adversarial jailbreaks, indirect prompt injection, and system override attempts. Triggers immediate hard termination upon malicious input detection. |
| **3** | **PII Scan Agent** | Privacy & Security | **Deterministic** | Utilizes Microsoft Presidio and pattern recognition to detect and redact personally identifiable information (names, emails, German IBANs, phone numbers) prior to downstream processing. |
| **4** | **EU AI Act Classifier Agent** | Legal Analysis | **LLM-Based** | Performs statutory risk classification against Regulation (EU) 2024/1689. Classifies systems into Prohibited (Art. 5), High-Risk (Art. 6 & Annex III), Limited-Risk (Art. 50), or Minimal-Risk, citing exact Articles. |
| **5** | **BaFin Compliance Agent** | Supervisory Analysis | **LLM-Based** | Evaluates systems against German supervisory mandates: MaRisk AT 4.3.2 (model risk management), KWG § 25a (internal controls), WpHG requirements, and BaFin BDAI circulars. Runs concurrently with the EU Classifier. |
| **6** | **Clarification Agent** | Human Interaction | **LLM-Based** | Triggered automatically when classification confidence falls below 0.60. Generates targeted technical questions to resolve statutory ambiguities. |
| **7** | **Translation Agent** | Multilingual Processing | **LLM-Based** | Translates authentic German regulatory texts (KWG, MaRisk) into English for reporting, while appending mandatory legal disclaimers preserving German statutory primacy. |
| **8** | **Conflict Resolution Agent** | Legal Synthesis | **LLM-Based** | Resolves tensions between EU-level standards and national supervisory circulars, establishing precedence hierarchies and unified compliance obligations. |
| **9** | **Gap Assessment Agent** | Audit & Gap Analysis | **LLM-Based** | Cross-references regulatory requirements against user-provided internal controls to produce categorized, prioritized compliance gaps with concrete remediation steps. |
| **10** | **Critic / QA Agent** | Verification & Grounding | **LLM-Based** | Independent auditor agent that cross-checks cited statutory articles against ingested knowledge base passages to eliminate hallucinations. Implements a retry circuit breaker (max 2 retries). |
| **11** | **Report Drafting Agent** | Document Generation | **LLM-Based** | Synthesizes all agent outputs into a standardized, executive-ready compliance evaluation report. |
| **12** | **Human-in-the-Loop Review Gate** | Governance & Sign-off | **Deterministic** | Enforces mandatory human oversight. Holds execution until a qualified compliance officer signs off, requests an agent revision, or rejects the assessment. |

---

## 🧭 Multi-Provider LLM Router Architecture

The `backend/llm_router` layer provides fault-tolerant inference across multiple model providers without vendor lock-in.

### Purpose and Aim
- **High Availability:** Automatically falls back across provider backends (Groq $\rightarrow$ Google Gemini $\rightarrow$ OpenRouter) when encountering rate limits (HTTP 429), server timeouts, or context exhaustion.
- **Provider Normalization:** Exposes a uniform asynchronous `complete()` interface returning a standardized `LLMResponse` dataclass with normalized token counts, latencies, and metadata.
- **Dynamic Model Allocation:** Allows individual agents to utilize specialized model configurations tuned for their specific reasoning complexity.

### Configuration via `.env`
Fallback cascades are configured directly via comma-delimited `provider:model` strings in `.env`. The router supports multiple inference providers (such as Groq, Google Gemini, and OpenRouter), where the exact model names can be customized and swapped depending on the operational scope, latency requirements, or reasoning depth needed (including larger models where appropriate):

```env
# Primary classifier routing chain across inference providers
ROUTER_CLASSIFIER_MODELS=groq:<model_name>,gemini:<model_name>,openrouter:<model_name>

# Fast-path security filter routing chain
ROUTER_GUARD_MODELS=groq:<model_name>,gemini:<model_name>,openrouter:<model_name>

# Executive report drafting chain
ROUTER_REPORT_MODELS=groq:<model_name>,gemini:<model_name>,openrouter:<model_name>
```

The router dynamically parses the chain, attempts inference on the primary provider, and seamlessly cascades to secondary providers if an upstream failure or rate limit occurs, recording all failover events in the database audit log. Model names can be scaled up or down per agent based on implementation needs.

---

## 🏗️ Functional Backend & Frontend Architecture

KonformAI is organized into modular subsystems:

```
KonformAI/
├── backend/
│   ├── api/            # REST API endpoints & route controllers (FastAPI)
│   ├── core/           # Configuration, security middleware, and logging setup
│   ├── db/             # Database session lifecycle, ORM schemas, and migrations
│   ├── llm_router/     # Multi-provider client abstraction & token management
│   ├── rag/            # Multilingual hybrid retrieval engine (Dense + Lexical)
│   ├── tools/          # External tool definitions & API integrations
│   ├── agents/         # LangGraph state graph and specialized agent implementations
│   └── observability/  # Audit logging, LangSmith tracing, and OpenTelemetry
├── frontend/           # Multi-screen Streamlit compliance dashboard
├── knowledge_base/     # Authoritative EU & German statutory documents
├── data/               # Demonstration cases and evaluation fixtures
└── scripts/            # Database initialization and automated ingestion utilities
```

### 1. Backend Core (`backend/core`)
- **`config.py`**: Centralized Pydantic `Settings` handling environment variables, API keys, database URLs, token budgets, and per-agent router cascades.
- **`security.py`**: API key dependency injection, cryptographic token hashing, rate-limiting, and request sanitization.
- **`logging_config.py`**: Structured JSON logging formatters with contextual correlation IDs for request traceability.

### 2. Database & Persistence Layer (`backend/db`)
- **Dual-Engine Auto-Fallback**: Automatically detects whether PostgreSQL 16 is accessible via a rapid socket probe. If PostgreSQL is unavailable, it seamlessly initializes and persists to a local SQLite database (`konformai.db`), allowing deployment anywhere without database prerequisites.
- **ORM Models (`models.py`)**: Defines schemas for `Case` records, `AuditLog` events, `LLMCallLog` metrics, `HumanReviewDecision` governance trails, and `KnowledgeBaseDocument` records.
- **Alembic Migrations**: Fully configured database versioning under `backend/db/migrations/`.

### 3. Retrieval-Augmented Generation (`backend/rag`)
- **Hybrid Retrieval (`hybrid_retriever.py`)**: Combines dense semantic vector retrieval with language-specific lexical search using an inline Reciprocal Rank Fusion (RRF) algorithm (40% BM25, 60% dense vector weight).
- **Multilingual Embeddings (`embeddings.py`)**: Employs BAAI/bge-m3 for dense multilingual representations across German and English legal terminology, with automated fallback handlers.
- **Hierarchical Document Ingestion (`ingestion.py`)**: Splits legal texts along natural structural boundaries (Article, Paragraph, Section) to preserve complete statutory context.

### 4. External Integrations & Tool Calling (`backend/tools`)
- **EUR-Lex SPARQL Integration (`eurlex_tool.py`)**: Direct programmatic connection to the EU Publications Office CELLAR SPARQL endpoint to verify authoritative CELEX identifiers and statutory amendments.
- **BaFin Registry Lookup Tool (`bafin_lookup_tool.py`)**: Validates supervised institution authorization statuses, banking categories (Vollbank, CRR-Kreditinstitut), and applicable supervisory obligations.
- **Microsoft Presidio Tool (`presidio_tool.py`)**: PII detection and redaction engine enforcing data privacy before document embedding and processing.
- **Security Notifier (`discord_notifier.py`)**: Automated webhook dispatch alerting security and compliance teams upon Article 5 violations or prompt injection attempts.

### 5. Frontend Dashboard (`frontend/streamlit_app.py`)
- **Screen 1 — Intake & Assessment**: Structured input forms, pre-loaded banking system templates, and document upload interfaces.
- **Screen 2 — Human-in-the-Loop Review**: Granular review screens displaying risk determinations, statutory citations, gap tables, and interactive approval/revision buttons.
- **Screen 3 — Knowledge Base Management**: File upload hub with integrated PII redaction and real-time vector re-indexing.
- **Screen 4 — Observability & Audit Trail**: Real-time inspection of immutable audit events, token usage breakdowns, latency distributions, and LangSmith execution traces.

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
| **Execution Mode** | `GLOBAL_DRY_RUN` | **Yes** | Set to `false` for live real-world LLM calls, or `true` for deterministic offline testing and automated CI verification. |
| **LLM Providers** | `GROQ_API_KEY` | Optional* | Inference API key from [console.groq.com](https://console.groq.com). |
| | `GOOGLE_API_KEY` | Optional* | Gemini API key from [aistudio.google.com](https://aistudio.google.com). Supports `gemini-3.6-flash`. |
| | `OPENROUTER_KEY` | Optional* | OpenRouter gateway key from [openrouter.ai](https://openrouter.ai). |
| **LLM Router Chains** | `ROUTER_*_MODELS` | Defaulted | Fallback cascades per agent, e.g. `groq:<model_name>,gemini:<model_name>,openrouter:<model_name>`. |
| **Observability** | `LANGCHAIN_TRACING_V2` | Optional | Set `true` to trace agent execution graphs. |
| | `LANGCHAIN_API_KEY` | Optional | Tracing API key from [smith.langchain.com](https://smith.langchain.com). *If left empty, tracing auto-disables to prevent 401 warnings.* |
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

## 🐳 Docker Containerization & Hub Publishing

KonformAI provides a **dual-mode deployment architecture** packaged inside a unified, production-grade multi-stage Docker container (`python:3.11-slim`):

1. **Standalone All-in-One Container (`entrypoint.sh`):**
   - Automatically initializes the database, ingests the regulatory knowledge base (`ingest_kb.py`), and seeds demo financial systems (`seed_demo_data.py`).
   - Concurrently spawns the **FastAPI backend** (port `8000`) and the **Streamlit dashboard** (port `8501`).
   - Uses SQLite auto-fallback so evaluators can test the entire stack with zero external database dependencies.
2. **Multi-Container Compose (`docker-compose.yml`):**
   - Coordinates separate services for **PostgreSQL 16 with PGVector (`db`)**, knowledge base ingestion (`ingestion`), FastAPI backend (`backend`), and Streamlit frontend (`frontend`).

### 1. Building and Pushing to Docker Hub

```bash
# 1. Login to Docker Hub
docker login

# 2. Build multi-stage production image locally
docker build -t your-dockerhub-username/konformai:latest .

# 3. Push pre-built image to Docker Hub registry
docker push your-dockerhub-username/konformai:latest
```

### 2. Pulling and Running from Docker Hub (Evaluator Quickstart)

Anyone on any machine (macOS, Windows, Linux) can run the full product with a single command:

```bash
# Pull the latest image
docker pull your-dockerhub-username/konformai:latest

# Run the unified stack (exposes UI on :8501 and API on :8000)
docker run -d -p 8501:8501 -p 8000:8000 -e GLOBAL_DRY_RUN=true your-dockerhub-username/konformai:latest
```

Access the application immediately at:
- **Streamlit Dashboard:** [http://localhost:8501](http://localhost:8501)
- **FastAPI OpenAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## ⚖️ Legal & Statutory Disclaimers

> [!IMPORTANT]
> **Not Legal Advice:** KonformAI is an automated agentic compliance-support tool and does not provide formal legal advice. Final regulatory classifications and supervisory filings must be reviewed and signed off by qualified legal counsel.

> [!NOTE]
> **German Translation Authority:** In accordance with German administrative law and BaFin supervisory practice, all English translations of German statutory texts (KWG, WpHG, MaRisk) are provided for information and convenience only. The German original text is the sole legally binding authority in all respects.
