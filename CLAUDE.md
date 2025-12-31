# CLAUDE.md - AI Assistant Guidelines for mini_me

## Project Overview

**mini_me** (Daily Report GA4 Agent) is an automation system for extracting data from Google Analytics 4 and generating daily email reports using an AI Agent powered by Anthropic Claude.

### Core Functionality
1. **Data Extraction**: Pull metrics from GA4 API → Store in SQLite/PostgreSQL → Cache in Redis
2. **AI Generation**: Use Claude (via datapizza-ai) to generate email reports based on GA4 data
3. **Approval Workflow**: Human-in-the-loop review and approval of generated emails
4. **Dashboard**: React frontend for visualization and management

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (React 19)                      │
│   Dashboard │ EmailGenerator │ BackfillPanel │ PromoDash    │
│                   Vite + TailwindCSS + Recharts              │
└─────────────────────────────┬───────────────────────────────┘
                              │ HTTP/REST
┌─────────────────────────────▼───────────────────────────────┐
│                     API LAYER (Flask)                        │
│    /api/generate │ /api/approve │ /api/stats │ /api/auth    │
│              JWT Authentication + CORS                       │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                  WORKFLOW SERVICE LAYER                      │
│  ExtractionStep → GenerationStep → ApprovalStep             │
│        Dependency Injection + Typed Results                  │
└──────────┬───────────────────┬───────────────────┬──────────┘
           │                   │                   │
    ┌──────▼──────┐    ┌───────▼───────┐   ┌──────▼──────┐
    │ GA4 Extract │    │   AI Agent    │   │   Storage   │
    │ Google API  │    │ datapizza-ai  │   │ SQLite/PG   │
    │ Extractors  │    │ Claude Sonnet │   │   Redis     │
    └─────────────┘    └───────────────┘   └─────────────┘
```

---

## Directory Structure

```
mini_me/
├── backend/                    # Python backend
│   ├── agent/                  # AI Agent configuration
│   │   ├── agent.py           # Agent creation with memory
│   │   ├── tools.py           # Tool functions for AI (get_daily_report, etc.)
│   │   ├── prompt.py          # System prompt
│   │   └── examples.py        # Few-shot learning loader
│   │
│   ├── ga4_extraction/        # GA4 data extraction layer
│   │   ├── database.py        # SQLite/PostgreSQL operations
│   │   ├── redis_cache.py     # Redis caching
│   │   ├── extraction.py      # GA4 API calls
│   │   ├── extractors/        # Modular extractors (backfill, campaigns, channels)
│   │   ├── factory.py         # Resource factory (DI pattern)
│   │   └── services.py        # Business logic
│   │
│   ├── workflows/             # Workflow orchestration
│   │   ├── service.py         # DailyReportWorkflow orchestrator
│   │   ├── config.py          # Configuration loader
│   │   ├── interfaces.py      # Protocol definitions (for DI)
│   │   ├── result_types.py    # Typed result classes
│   │   └── steps/             # Workflow steps
│   │       ├── extraction.py  # Step 1: GA4 → Database
│   │       ├── generation.py  # Step 2: AI → Draft
│   │       └── approval.py    # Step 3: Archive + History
│   │
│   ├── api.py                 # Flask REST API (main entry point)
│   ├── main.py                # CLI orchestrator
│   ├── db_pool.py             # Connection pooling
│   └── scripts/               # Utility scripts
│
├── src/                       # React frontend
│   ├── components/
│   │   ├── Dashboard.jsx      # SWI/CR charts (Recharts)
│   │   ├── EmailGenerator.jsx # Generate/preview/approve UI
│   │   ├── BackfillPanel.jsx  # Data recovery tool
│   │   └── PromoDashboard.jsx # Promo calendar visualization
│   ├── context/               # React contexts (Auth, Backfill, Promo)
│   ├── services/api.js        # Axios API client
│   └── utils/                 # Helpers (logger, cache)
│
├── api/                       # Vercel serverless functions
├── config.yaml                # Main configuration file
├── history.md                 # Approved emails (few-shot examples)
├── data/                      # SQLite database (git-ignored)
├── email/                     # Draft & archive (git-ignored)
└── credentials/               # OAuth tokens (git-ignored)
```

---

## Tech Stack

### Backend
| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.12+ | Backend runtime |
| Flask | 3.x | REST API framework |
| datapizza-ai | 0.0.7+ | AI Agent framework |
| Anthropic Claude | claude-sonnet-4-5 | LLM for email generation |
| Google Analytics Data API | 0.19+ | GA4 metrics extraction |
| SQLite / PostgreSQL | - | Persistent storage |
| Redis | 5.x+ | Cache + Agent memory |
| PyJWT | 2.8+ | JWT authentication |
| Gunicorn | 21+ | Production WSGI server |

### Frontend
| Component | Version | Purpose |
|-----------|---------|---------|
| React | 19.x | UI framework |
| Vite | 7.x | Build tool & dev server |
| TailwindCSS | 3.x | Utility-first styling |
| Recharts | 3.x | Data visualization |
| React Router | 7.x | Client-side routing |
| Axios | 1.x | HTTP client |

---

## Development Commands

### Backend
```bash
# Install dependencies (uses uv package manager)
uv sync

# Run API server (dev mode, port 5001)
uv run backend/api.py

# Run CLI workflow
uv run backend/main.py

# Database setup
uv run backend/scripts/setup_database.py

# Backfill historical data
uv run backend/scripts/backfill_missing_dates.py --start-date 2025-10-01

# Run tests
uv run pytest
```

### Frontend
```bash
# Install dependencies
npm install

# Dev server (port 5173)
npm run dev

# Build for production
npm run build

# Lint
npm run lint
```

### Full Stack Local
```bash
# Start Redis + Backend + Frontend
./scripts/start-local-server.sh
```

---

## API Endpoints

### Authentication
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/login` | POST | No | Login → JWT token |
| `/api/auth/logout` | POST | No | Clear auth cookie |

### Core Workflow
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/health` | GET | No | Health check |
| `/api/stats` | GET | JWT | Database statistics |
| `/api/generate` | POST | JWT | Extract GA4 + Generate email |
| `/api/draft` | GET | JWT | Read current draft |
| `/api/approve` | POST | JWT | Archive + update history |
| `/api/reject` | POST | JWT | Delete current draft |

### Data Management
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/backfill` | POST | JWT | Backfill date range |
| `/api/metrics/range` | GET | JWT | Metrics for date range |
| `/api/sessions/range` | GET | JWT | Sessions by channel |

---

## Configuration

### Environment Variables (.env)
```env
# Required
ANTHROPIC_API_KEY=your_anthropic_api_key
PROPERTY_ID=your_ga4_property_id

# Authentication
STAGING_USER=admin
STAGING_PASSWORD=secure_password
JWT_SECRET_KEY=your_jwt_secret

# Optional - Redis (production)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_TOKEN=your_redis_password  # For Upstash/Redis Cloud
REDIS_SSL=true                    # Enable for cloud Redis

# Optional - API Security
API_SECRET_KEY=your_api_secret_key

# Production
CORS_ORIGINS=https://your-frontend.vercel.app
```

### config.yaml Key Sections
- `agent.model`: LLM model to use (default: `claude-sonnet-4-5-20250929`)
- `database.sqlite.path`: SQLite database path
- `database.redis`: Redis connection settings
- `execution.output_dir`: Where to save drafts
- `examples.source_file`: Few-shot examples file (history.md)

---

## Code Conventions

### Python (Backend)
- **Python 3.12+** required
- **Type hints** on all function signatures
- **Docstrings** for public functions (Google style)
- **SOLID principles**: Dependency Injection for testability
- **Error handling**: Use typed result classes, not exceptions for control flow
- **Naming**: snake_case for functions/variables, PascalCase for classes

### JavaScript/React (Frontend)
- **React 19** with hooks
- **Functional components** only (no class components)
- **Memoization** for expensive components (React.memo, useMemo, useCallback)
- **Lazy loading** for heavy components (Dashboard, PromoDashboard)
- **Naming**: camelCase for variables/functions, PascalCase for components

### API Design
- REST endpoints follow `/api/{resource}` pattern
- POST for mutations, GET for queries
- JSON responses with `{success: bool, data?: any, error?: string}`
- JWT in HttpOnly cookie (same-domain) + Bearer token fallback (cross-domain)

---

## Key Patterns

### Workflow Orchestration
The `DailyReportWorkflow` class in `backend/workflows/service.py` orchestrates the 3-step pipeline:
1. **ExtractionStep**: Query GA4 API → Store in database
2. **GenerationStep**: Load examples → Call AI Agent → Save draft
3. **ApprovalStep**: Archive email → Update history.md

Each step implements a Protocol interface for dependency injection and testing.

### AI Agent Tools
The agent has access to these tools (defined in `backend/agent/tools.py`):
- `get_daily_report()`: Get metrics for a specific date
- `get_weekend_report()`: Get Friday-Sunday recap
- `compare_periods()`: Compare two date ranges
- `get_active_promos()`: Check active promotions
- `compare_promo_periods()`: Compare metrics with different promos

### Database Access Pattern
```python
# Use connection pooling (backend/db_pool.py)
from backend.db_pool import get_pool

# In Flask routes, connections are per-request via Flask 'g'
db = get_db()  # Returns pooled connection
```

### Error Handling in API
```python
@handle_errors  # Decorator catches exceptions → JSON error response
def my_endpoint():
    # Errors return {success: false, error: "...", error_type: "..."}
    pass
```

---

## Testing

### Backend Tests
```bash
# Run all tests
uv run pytest

# With coverage
uv run pytest --cov=backend

# Specific test file
uv run pytest tests/test_tools.py -v
```

### Mocking for Tests
The workflow uses Protocol-based interfaces for dependency injection:
```python
# In tests, inject mock steps
mock_extraction = MockExtractionStep()
workflow = DailyReportWorkflow(config, extraction_step=mock_extraction)
```

---

## Deployment

### Vercel (Frontend + API)
- Frontend: Static files via `npm run build`
- API: Serverless functions in `/api` directory
- Config: `vercel.json` for routing

### Production Considerations
- **Redis**: Use Upstash or Redis Cloud (set REDIS_HOST, REDIS_TOKEN, REDIS_SSL)
- **Database**: PostgreSQL recommended for production (psycopg2 installed)
- **CORS**: Set CORS_ORIGINS for your frontend domain
- **JWT**: Always set JWT_SECRET_KEY in production

---

## Common Tasks

### Add a New API Endpoint
1. Add route in `backend/api.py` under `register_routes()`
2. Use `@handle_errors` decorator for consistent error handling
3. Use `@require_api_key` for protected endpoints
4. Add corresponding method in `src/services/api.js`

### Add a New Agent Tool
1. Add function in `backend/agent/tools.py`
2. Decorate with `@tool` from datapizza
3. Add to `available_tools` list in `backend/agent/agent.py`
4. Document in prompt if needed

### Add a New React Component
1. Create in `src/components/`
2. Use functional component with hooks
3. Add route in `src/App.jsx` if it's a page
4. Use lazy loading for heavy components

### Modify GA4 Extraction
1. Extractors are in `backend/ga4_extraction/extractors/`
2. Each extractor inherits from `BaseExtractor`
3. Register in `backend/ga4_extraction/extractors/registry.py`

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Redis not available | Start Redis: `redis-server &` |
| Empty database | Run backfill: `uv run backend/scripts/backfill_missing_dates.py` |
| GA4 auth expired | Delete `credentials/token.json`, re-authenticate |
| Agent not generating | Check `logs/agent_execution.log` |
| Frontend not loading | Verify backend running on port 5001 |
| JWT errors | Check JWT_SECRET_KEY is set |

---

## File Locations Quick Reference

| Purpose | Location |
|---------|----------|
| Main API entry | `backend/api.py` |
| CLI entry | `backend/main.py` |
| AI Agent config | `backend/agent/agent.py` |
| AI Tools | `backend/agent/tools.py` |
| Workflow service | `backend/workflows/service.py` |
| Database operations | `backend/ga4_extraction/database.py` |
| React entry | `src/main.jsx` |
| App routing | `src/App.jsx` |
| API client | `src/services/api.js` |
| Config | `config.yaml` |
| Few-shot examples | `history.md` |

---

## Security Notes

- Never commit `.env`, `credentials/`, or `*.db` files
- JWT tokens expire after 30 days (configurable in `JWT_EXPIRATION_DAYS`)
- CORS whitelist is enforced in production
- Rate limiting on login endpoint (5 attempts per 5 minutes)
- Use constant-time comparison for credential validation

---

*Last Updated: 2025-12-31*
*Version: 5.1.0*
