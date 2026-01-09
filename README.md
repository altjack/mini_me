# Daily Report GA4 Agent

Sistema di automazione per l'estrazione dati da Google Analytics 4 e generazione di report email giornalieri tramite AI Agent.

---

## 📐 Architettura di Sistema

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                   FRONTEND LAYER                                    │
│                                                                                     │
│    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│    │  Dashboard  │    │   Email     │    │  Backfill   │    │   Promo     │        │
│    │  (Recharts) │    │  Generator  │    │   Panel     │    │  Dashboard  │        │
│    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘        │
│           │                  │                  │                  │               │
│           └──────────────────┴────────┬─────────┴──────────────────┘               │
│                                       │                                            │
│                        React 19 + Vite + TailwindCSS                               │
└───────────────────────────────────────┼────────────────────────────────────────────┘
                                        │ HTTP/REST
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    API LAYER                                        │
│                                                                                     │
│                              Flask + JWT Auth                                       │
│    ┌─────────────────────────────────────────────────────────────────────────┐     │
│    │  /api/health  │  /api/stats  │  /api/generate  │  /api/approve  │  ...  │     │
│    └─────────────────────────────────────────────────────────────────────────┘     │
│                                       │                                            │
└───────────────────────────────────────┼────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               WORKFLOW SERVICE LAYER                                │
│                                                                                     │
│    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐               │
│    │  Extraction     │ ─► │   Generation    │ ─► │    Approval     │               │
│    │     Step        │    │      Step       │    │      Step       │               │
│    │                 │    │                 │    │                 │               │
│    │  GA4 → SQLite   │    │  AI → Draft.md  │    │  Archive + Mem  │               │
│    └────────┬────────┘    └────────┬────────┘    └────────┬────────┘               │
│             │                      │                      │                        │
│             │    DailyReportWorkflow Orchestrator         │                        │
│             │    (Dependency Injection, Typed Results)    │                        │
└─────────────┼──────────────────────┼──────────────────────┼────────────────────────┘
              │                      │                      │
              ▼                      ▼                      ▼
┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────────────┐
│   GA4 EXTRACTION      │ │      AI AGENT         │ │      STORAGE LAYER            │
│                       │ │                       │ │                               │
│  ┌─────────────────┐  │ │  ┌─────────────────┐  │ │  ┌───────────┐ ┌───────────┐  │
│  │ Google Analytics│  │ │  │  datapizza-ai   │  │ │  │  SQLite   │ │   Redis   │  │
│  │   Data API      │  │ │  │   Framework     │  │ │  │   (DB)    │ │  (Cache)  │  │
│  └────────┬────────┘  │ │  └────────┬────────┘  │ │  └─────┬─────┘ └─────┬─────┘  │
│           │           │ │           │           │ │        │             │        │
│  ┌────────┴────────┐  │ │  ┌────────┴────────┐  │ │  ga4_data.db    Agent Memory  │
│  │  Extractors     │  │ │  │ Anthropic Claude│  │ │                               │
│  │  - Daily Metrics│  │ │  │ claude-sonnet-4 │  │ │  ┌───────────────────────┐    │
│  │  - Channels     │  │ │  └─────────────────┘  │ │  │     history.md        │    │
│  │  - Campaigns    │  │ │                       │ │  │  (Few-shot Examples)  │    │
│  │  - Backfill     │  │ │  Tools:               │ │  └───────────────────────┘    │
│  └─────────────────┘  │ │  • get_daily_report   │ │                               │
│                       │ │  • get_weekend_report │ │  ┌───────────────────────┐    │
│  Rate Limiter         │ │  • compare_periods    │ │  │    email/archive/     │    │
│  Retry Logic          │ │  • get_active_promos  │ │  │  (Approved Emails)    │    │
│                       │ │  • compare_promo_...  │ │  └───────────────────────┘    │
└───────────────────────┘ └───────────────────────┘ └───────────────────────────────┘
```

### Flow Diagram

```
  User Action                     Backend Process                      Result
  ───────────                     ───────────────                      ──────

  [Generate]  ─────────►  ┌─────────────────────────────┐
     │                    │  1. ExtractionStep          │
     │                    │     - Query GA4 API         │
     │                    │     - Store in SQLite       │       ┌──────────────┐
     │                    │     - Cache in Redis        │ ────► │ Data Ready   │
     │                    └─────────────────────────────┘       └──────────────┘
     │                                  │
     │                                  ▼
     │                    ┌─────────────────────────────┐
     │                    │  2. GenerationStep          │
     │                    │     - Load examples         │
     │                    │     - Call AI Agent         │       ┌──────────────┐
     │                    │     - Generate draft        │ ────► │ draft_email  │
     │                    └─────────────────────────────┘       │     .md      │
     │                                                          └──────────────┘
     ▼
  [Approve]   ─────────►  ┌─────────────────────────────┐
                          │  3. ApprovalStep            │
                          │     - Archive email         │       ┌──────────────┐
                          │     - Update history.md     │ ────► │ Email Sent   │
                          │     - Store in Redis mem    │       └──────────────┘
                          └─────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Backend

| Component | Version | Purpose |
|-----------|---------|---------|
| **Python** | 3.12+ | Backend runtime |
| **Flask** | 3.x | REST API framework |
| **datapizza-ai** | 0.0.7+ | AI Agent framework proprietario |
| **Anthropic Claude** | claude-sonnet-4-5 | LLM per generazione email |
| **Google Analytics Data API** | 0.19+ | Estrazione metriche GA4 |
| **PyJWT** | 2.8+ | Autenticazione JWT |
| **Gunicorn** | 21+ | Production WSGI server |

### Frontend

| Component | Version | Purpose |
|-----------|---------|---------|
| **React** | 19.x | UI framework |
| **Vite** | 7.x | Build tool & dev server |
| **TailwindCSS** | 3.x | Styling utility-first |
| **Recharts** | 3.x | Data visualization |
| **React Router** | 7.x | Client-side routing |
| **Axios** | 1.x | HTTP client |
| **Lucide React** | 0.5+ | Icon library |

### Storage & Infrastructure

| Component | Version | Purpose |
|-----------|---------|---------|
| **SQLite** | 3.x | Persistent storage metriche GA4 |
| **Redis** | 7.x | Cache layer + Agent memory |
| **uv** | latest | Python package manager |

### External Services

| Service | Purpose |
|---------|---------|
| **Anthropic API** | Claude LLM per generazione contenuti |
| **Google Analytics 4 API** | Estrazione dati traffico e conversioni |

---

## 📁 Struttura Progetto

```
daily_report/
├── backend/
│   ├── agent/                    # AI Agent (Claude)
│   │   ├── agent.py              # Agent configuration
│   │   ├── tools.py              # Tool functions per AI
│   │   ├── prompt.py             # System prompt
│   │   └── examples.py           # Few-shot learning loader
│   │
│   ├── ga4_extraction/           # Data extraction layer
│   │   ├── database.py           # SQLite operations
│   │   ├── redis_cache.py        # Redis caching
│   │   ├── extraction.py         # GA4 API calls
│   │   ├── extractors/           # Modular extractors
│   │   │   ├── backfill.py       # Historical data
│   │   │   ├── campaigns.py      # Campaign metrics
│   │   │   └── channels.py       # Channel sessions
│   │   ├── factory.py            # Resource factory (DI)
│   │   ├── services.py           # Business logic
│   │   └── rate_limiter.py       # API rate limiting
│   │
│   ├── workflows/                # Workflow orchestration
│   │   ├── service.py            # DailyReportWorkflow
│   │   ├── config.py             # Configuration loader
│   │   ├── interfaces.py         # Protocol definitions
│   │   ├── result_types.py       # Typed results
│   │   └── steps/                # Workflow steps
│   │       ├── extraction.py     # Step 1: GA4 → SQLite
│   │       ├── generation.py     # Step 2: AI → Draft
│   │       └── approval.py       # Step 3: Archive
│   │
│   ├── api.py                    # Flask REST API
│   ├── db_pool.py                # Connection pooling
│   └── migrations/               # Database migrations
│
├── src/                          # Frontend (React)
│   ├── components/
│   │   ├── Dashboard.jsx         # Charts & metrics
│   │   ├── EmailGenerator.jsx    # Generate/preview/approve
│   │   ├── BackfillPanel.jsx     # Data recovery
│   │   └── LoginPage.jsx         # Authentication
│   ├── services/api.js           # API client
│   ├── context/AuthContext.jsx   # Auth state
│   └── utils/                    # Helpers
│
├── data/                         # SQLite database
├── email/                        # Drafts & archive
├── logs/                         # Application logs
├── config.yaml                   # Configuration
└── history.md                    # Approved emails (few-shot)
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Python dependencies (usa uv)
uv sync

# Redis (macOS)
brew install redis
redis-server &

# Frontend dependencies
cd frontend && npm install && cd ..
```

### 2. Configuration

Crea file `.env`:
```env
ANTHROPIC_API_KEY=your_api_key_here
STAGING_USER=admin
STAGING_PASSWORD=your_secure_password
JWT_SECRET_KEY=your_jwt_secret
```

Assicurati che `credentials/token.json` esista per OAuth GA4.

### 3. Initialize Database

```bash
uv run backend/scripts/setup_database.py
```

### 4. Backfill Historical Data (prima esecuzione)

```bash
uv run backend/scripts/backfill_missing_dates.py --start-date 2025-10-01
```

---

## 🖥️ Running the Application

### Avvio Completo (Script)

```bash
# Avvia Redis + Backend + Frontend
./scripts/start-local-server.sh
```

### Avvio Manuale

```bash
# Backend API (porta 5001)
uv run backend/api.py

# Frontend dev server (porta 5173)
npm run dev
```

### Riavvio Backend (dopo modifiche al codice)

Se hai modificato file Python nel backend, devi riavviare il server per applicare le modifiche:

```bash
# Metodo 1: Stop e restart completo
./scripts/stop-local-server.sh
./scripts/start-local-server.sh

# Metodo 2: Riavvio solo del backend (se avviato manualmente)
# Trova il processo e terminalo
pkill -f "backend/api.py"
# Riavvia
uv run backend/api.py

# Metodo 3: Con Gunicorn (production)
pkill -f gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 backend.api:app
```

> **Nota:** Il frontend (Vite) supporta l'hot-reload automatico, quindi non è necessario riavviarlo per le modifiche ai file React/JSX.

### URLs

| Service | URL |
|---------|-----|
| **Frontend UI** | http://localhost:5173 |
| **Backend API** | http://localhost:5001 |
| **API Health** | http://localhost:5001/api/health |

---

## 🔌 API Endpoints

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login → JWT token |
| `/api/auth/logout` | POST | Logout → clear cookie |

### Core Workflow

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/health` | GET | No | Health check |
| `/api/stats` | GET | Yes | Database statistics |
| `/api/generate` | POST | Yes | Extract GA4 + Generate email |
| `/api/draft` | GET | Yes | Read current draft |
| `/api/approve` | POST | Yes | Approve → archive + history |
| `/api/reject` | POST | Yes | Delete current draft |

### Data Management

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/backfill` | POST | Yes | Backfill date range |
| `/api/workflow/full` | POST | Yes | Full workflow (auto-approve) |
| `/api/metrics/range` | GET | Yes | Metrics for date range |
| `/api/sessions/range` | GET | Yes | Sessions breakdown |

---

## 🌐 Web UI Features

| Feature | Description |
|---------|-------------|
| **Dashboard** | Grafici interattivi SWI, CR, sessioni per canale |
| **Generate Report** | One-click GA4 extraction + AI email generation |
| **Draft Preview** | Live markdown rendering con syntax highlighting |
| **Approve/Reject** | Workflow approvazione → archivia + aggiorna history |
| **Backfill** | Recupero dati storici per range di date |
| **Promo Dashboard** | Visualizzazione calendario promozioni |

---

## 💻 CLI Commands

### Main Orchestrator

```bash
# Full workflow (interactive approval)
uv run backend/main.py

# Auto-approve mode
uv run backend/main.py --auto-approve

# Specific date
uv run backend/main.py --date 2025-12-01 --force
```

### Data Management

```bash
# Backfill missing dates
uv run backend/scripts/backfill_missing_dates.py --start-date 2025-11-01

# Single date
uv run backend/scripts/backfill_missing_dates.py --date 2025-12-01

# Channel data (D-2 delay)
uv run backend/scripts/extract_channels_delayed.py --days 7
```

---

## 🔧 Configuration

Configurazione principale in `config.yaml`:

```yaml
agent:
  model: "claude-sonnet-4-5-20250929"
  verbose: true

database:
  sqlite:
    path: "data/ga4_data.db"
  redis:
    host: "localhost"
    port: 6379
    db: 1
    ttl_days: 21

execution:
  output_dir: "email"
  draft_filename: "draft_email.md"
  archive_dir: "email/archive"

examples:
  source_file: "history.md"
  sample_size: 15
  sampling_strategy: "recent_weighted"
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Redis not available | `redis-server &` |
| Empty database | `uv run backend/scripts/backfill_missing_dates.py` |
| GA4 auth expired | Delete `credentials/token.json`, re-auth |
| Agent not generating | Check `logs/agent_execution.log` |
| Frontend not loading | Verify backend running on port 5001 |

---

**Version:** 5.0.0  
**Last Updated:** 2025-12-19
