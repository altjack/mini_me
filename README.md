# Daily Report GA4 Agent

Automated GA4 data extraction and daily email generation with AI Agent.

---

## 🛠️ Tech Stack & Prerequisites

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Backend runtime |
| uv | latest | Python package manager |
| Redis | 7.x | Cache + Agent memory |
| Node.js | 20+ | Frontend runtime |
| SQLite | 3.x | Persistent storage |

**External Services:**
- Anthropic API (Claude claude-sonnet-4-5-20250929)
- Google Analytics 4 API

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Python dependencies
uv sync

# Redis (macOS)
brew install redis
redis-server &

# Frontend dependencies
cd frontend && npm install && cd ..
```

### 2. Configuration

Create `.env` file:
```env
ANTHROPIC_API_KEY=your_api_key_here
```

Ensure `credentials/token.json` exists for GA4 OAuth.

### 3. Initialize Database

```bash
uv run scripts/setup_database.py
```

### 4. Backfill Historical Data (first time only)

```bash
uv run scripts/backfill_missing_dates.py --start-date 2025-10-01
```

---

## 🖥️ Running the Application

### Start Backend API

```bash
uv run api.py
# Server: http://localhost:5001
```

### Start Frontend UI

```bash
cd frontend && npm run dev
# UI: http://localhost:5173
```

---

## 🌐 Web UI Features

| Feature | Description |
|---------|-------------|
| **Dashboard** | Real-time database statistics (records, date range, avg conversions) |
| **Generate Report** | One-click GA4 extraction + AI email generation |
| **Draft Preview** | Live markdown rendering of generated email |
| **Approve/Reject** | Approve → archives + adds to history.md + Redis memory |
| **Backfill** | Recover missing data for date ranges |

---

## 🔌 API Endpoints

Base URL: `http://localhost:5001`

### Health & Stats

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/stats` | GET | Database statistics |

**GET /api/stats Response:**
```json
{
  "record_count": 393,
  "min_date": "2024-11-06",
  "max_date": "2025-12-03",
  "avg_conversioni": 158,
  "latest_available_date": "2025-12-03"
}
```

### Email Workflow

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/generate` | POST | Extract GA4 + Generate email draft |
| `/api/draft` | GET | Read current draft |
| `/api/approve` | POST | Approve draft (archive + history) |
| `/api/reject` | POST | Delete current draft |

**POST /api/generate Response:**
```json
{
  "success": true,
  "content": "# Draft Email...",
  "data_date": "2025-12-03"
}
```

### Data Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/backfill` | POST | Backfill data for date range |
| `/api/workflow/full` | POST | Run complete workflow (extract → generate → approve) |

**POST /api/backfill Body:**
```json
{
  "start_date": "2025-11-01",
  "end_date": "2025-11-10"
}
```

---

## 🔄 Workflow Architecture

### Module Structure

```
workflows/
├── __init__.py
├── result_types.py    # StepStatus, StepResult, WorkflowResult
├── config.py          # ConfigLoader (YAML + validation)
├── logging.py         # LoggerFactory
├── interfaces.py      # Protocol definitions (DI)
├── service.py         # DailyReportWorkflow orchestrator
└── steps/
    ├── extraction.py  # ExtractionStep (GA4 data)
    ├── generation.py  # GenerationStep (AI Agent)
    └── approval.py    # ApprovalStep (archive + memory)
```

### Workflow Steps

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  ExtractionStep │ ──► │ GenerationStep  │ ──► │  ApprovalStep   │
│  (GA4 → SQLite) │     │ (AI → Draft)    │     │ (Archive+Redis) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Usage Examples

```python
from workflows.service import DailyReportWorkflow
from workflows.config import ConfigLoader

# Full workflow
config = ConfigLoader.load()
with DailyReportWorkflow(config) as workflow:
    result = workflow.run_full(auto_approve=True)
    
    if result.success:
        print(f"✅ Completed in {result.duration_seconds:.1f}s")
    else:
        print(f"❌ Errors: {result.errors}")

# Individual steps
with DailyReportWorkflow(config) as workflow:
    extraction = workflow.run_extraction(target_date="2025-12-03")
    generation = workflow.run_generation()
    approval = workflow.run_approval(interactive=False)
```

### Result Types

```python
class StepStatus(Enum):
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()  # Data already exists

@dataclass
class ExtractionResult(StepResult):
    date: str
    records_affected: int

@dataclass
class GenerationResult(StepResult):
    draft_path: str

@dataclass
class ApprovalResult(StepResult):
    archive_path: str
    added_to_memory: bool
```

---

## 💻 CLI Commands

### Main Orchestrator

```bash
# Full workflow (interactive approval)
uv run main.py

# Auto-approve mode
uv run main.py --auto-approve

# Specific date
uv run main.py --date 2025-12-01 --force
```

### Individual Steps

```bash
# Generate only (extraction + AI)
uv run run_agent.py

# Approve existing draft
uv run approve_draft.py
```

### Data Management

```bash
# Backfill missing dates
uv run scripts/backfill_missing_dates.py --start-date 2025-11-01

# Single date
uv run scripts/backfill_missing_dates.py --date 2025-12-01

# Channel data (D-2)
uv run scripts/extract_channels_delayed.py --days 7
```

---

## 📁 Project Structure

```
daily_report/
├── workflows/         # Workflow orchestration (NEW)
├── agent/             # AI Agent (tools, prompt, memory)
├── ga4_extraction/    # Data layer (SQLite, Redis, GA4 API)
├── frontend/          # React UI
├── scripts/           # Utility scripts
├── tests/             # Test suite
├── data/              # SQLite database
├── email/             # Drafts + archive
├── config.yaml        # Configuration
└── history.md         # Approved emails history
```

---

## 🔧 Configuration

Key settings in `config.yaml`:

```yaml
agent:
  model: "claude-sonnet-4-5-20250929"

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
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Redis not available | `redis-server &` |
| Empty database | `uv run scripts/backfill_missing_dates.py` |
| GA4 auth expired | Delete `credentials/token.json`, re-auth |
| Agent not generating | Check `agent_execution.log` |

---

**Version:** 4.0.0 (Workflow Service Layer)  
**Last Updated:** 2025-12-04
