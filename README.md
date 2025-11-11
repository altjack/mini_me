# Daily Report GA4 Agent

Sistema automatico per estrazione dati GA4 e generazione email giornaliere con AI Agent.

**Architettura SOLID** con storage ibrido SQLite + Redis per performance e persistenza ottimali.

---

## 🎯 Quick Start

```bash
# 1. Setup iniziale
uv sync
brew install redis && redis-server &

# 2. Inizializza database
uv run scripts/setup_database.py

# 3. Popola storico (60 giorni)
uv run scripts/backfill_missing_dates.py --start-date 2025-10-01

# 4. Workflow giornaliero
uv run main.py              # Estrazione dati GA4
uv run run_agent.py         # Generazione email AI
uv run approve_draft.py     # Approvazione draft
```

---

## 📋 Architettura

```
┌─────────────┐
│  Cron Job   │  Automatico giornaliero
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   main.py   │  Estrazione GA4 (D-1)
└──────┬──────┘
       │
       ├────────────────────────────────┐
       │                                 │
       ▼                                 ▼
┌──────────────┐                 ┌──────────────┐
│SQLite DB     │◄────sync────────│Redis Cache   │
│(permanente)  │                 │(14 giorni)   │
└──────┬───────┘                 └──────┬───────┘
       │                                 │
       └─────────────┬───────────────────┘
                     │
                     ▼
              ┌─────────────┐
              │Agent Tools  │  Read-through cache
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │run_agent.py │  Genera draft email
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │approve_draft│  Approvazione
              └─────────────┘
```

### Vantaggi

✅ **SOLID Architecture**: Factory pattern, service layer, dependency injection  
✅ **Zero CSV**: Storage normalizzato in SQLite  
✅ **Performance**: Redis cache per ultimi 14 giorni  
✅ **Flessibilità**: Comparison dinamici con qualsiasi periodo  
✅ **Manutenibilità**: Struttura modulare e testabile  

---

## 📁 Struttura Progetto

```
daily_report/
├── agent/                      # AI Agent modules
│   ├── agent.py               # Configurazione Anthropic
│   ├── tools.py               # Tool per accesso dati
│   ├── prompt.py              # System prompt
│   └── examples.py            # Gestione esempi storici
│
├── ga4_extraction/            # Data Layer (SOLID)
│   ├── database.py            # GA4Database (SQLite)
│   ├── redis_cache.py         # GA4RedisCache
│   ├── extraction.py          # Logica estrazione GA4
│   ├── factory.py             # GA4ResourceFactory
│   └── services.py            # GA4DataService
│
├── scripts/                   # Utility scripts
│   ├── setup_database.py      # Setup iniziale
│   ├── backfill_missing_dates.py  # Recupero dati
│   ├── extract_channels_delayed.py  # Canali D-2
│   └── cleanup.sh             # Pulizia temp files
│
├── tests/                     # Test suite
│   ├── test_integration.py    # Test sistema completo
│   ├── test_workflow.py       # Test workflow
│   └── test_channels.py       # Test canali
│
├── data/                      # Database SQLite
├── email/                     # Draft e archivio
├── logs/                      # Log files
├── credentials/               # GA4 credentials
│
├── main.py                    # Orchestrator principale
├── run_agent.py               # Agent runner
├── approve_draft.py           # Draft approval
├── config.yaml                # Configurazione
└── history.md                 # Storico email
```

---

## 🚀 Setup Completo

### 1. Installazione

```bash
# Installa dipendenze
uv sync

# Installa e avvia Redis
brew install redis
redis-server &

# Verifica Redis
redis-cli ping  # Output: PONG
```

### 2. Configurazione

Crea file `.env`:
```env
ANTHROPIC_API_KEY=your_api_key_here
```

### 3. Setup Database

```bash
uv run scripts/setup_database.py
```

Questo script:
- ✅ Crea directory `data/` e `logs/`
- ✅ Inizializza schema SQLite
- ✅ Verifica connessione Redis
- ✅ Configura TTL 14 giorni

### 4. Backfill Storico

```bash
# Popola ultimi 60 giorni
uv run scripts/backfill_missing_dates.py --start-date 2025-10-01

# Oppure recupera date specifiche
uv run scripts/backfill_missing_dates.py --date 2025-11-05
```

⏱️ Richiede ~10-15 minuti per 60 giorni

---

## 📊 Workflow Giornaliero

### Automatico (Cron)

```bash
# Estrazione dati principali (ogni giorno alle 8:00)
0 8 * * * cd /path/to/daily_report && uv run main.py

# Estrazione canali ritardata D-2 (ogni giorno alle 9:00)
0 9 * * * cd /path/to/daily_report && uv run scripts/extract_channels_delayed.py
```

### Manuale

```bash
# 1. Estrazione dati GA4 per ieri
uv run main.py

# 2. Generazione email con AI Agent
uv run run_agent.py

# 3. Review draft
cat email/draft_email.md

# 4. Approvazione
uv run approve_draft.py
```

---

## 🔄 Recupero Dati Mancanti

### Date Mancanti

```bash
# Recupera tutte le date mancanti (ultimi 60 giorni)
uv run scripts/backfill_missing_dates.py

# Range specifico
uv run scripts/backfill_missing_dates.py --start-date 2025-11-01 --end-date 2025-11-10

# Singola data
uv run scripts/backfill_missing_dates.py --date 2025-11-05
```

### Dati Canale Mancanti

```bash
# Solo sessioni per canale (D-2)
uv run scripts/backfill_missing_dates.py --only-channels

# Date mancanti + canali
uv run scripts/backfill_missing_dates.py --include-channels
```

### Estrazione Canali Manuale

```bash
# Data specifica
uv run scripts/extract_channels_delayed.py --date 2025-11-05

# Ultimi 7 giorni
uv run scripts/extract_channels_delayed.py --days 7
```

---

## 🛠️ Tool Agente

L'AI Agent ha accesso ai seguenti tool con **read-through cache**:

| Tool | Descrizione | Performance |
|------|-------------|-------------|
| `get_daily_report(date)` | Report completo giornaliero | 🚀 Redis cache |
| `get_metrics_summary(period_days)` | Metriche con comparison | 🚀 Redis cache |
| `get_product_performance(date)` | Performance prodotti | 🚀 Redis cache |
| `get_sessions_by_channel(date)` | Sessioni per canale | 🚀 Redis cache |

### Esempi

```python
# Report giornaliero
get_daily_report(date="2025-11-10")

# Metriche ultimi 7 giorni
get_metrics_summary(period_days=7)

# Performance prodotti
get_product_performance(date="2025-11-10")
```

---

## 🧪 Test

```bash
# Test integrazione completa
uv run tests/test_integration.py

# Test workflow
uv run tests/test_workflow.py

# Test canali
uv run tests/test_channels.py

# Test validazione date
uv run tests/test_date_validation.py
```

---

## 📝 Database

### Schema SQLite

```sql
-- Metriche giornaliere
CREATE TABLE daily_metrics (
    date DATE PRIMARY KEY,
    extraction_timestamp DATETIME,
    sessioni_commodity INTEGER,
    sessioni_lucegas INTEGER,
    swi_conversioni INTEGER,
    cr_commodity REAL,
    cr_lucegas REAL,
    cr_canalizzazione REAL,
    start_funnel INTEGER
);

-- Performance prodotti
CREATE TABLE products_performance (
    id INTEGER PRIMARY KEY,
    date DATE,
    product_name TEXT,
    total_conversions REAL,
    percentage REAL,
    UNIQUE(date, product_name)
);

-- Sessioni per canale
CREATE TABLE sessions_by_channel (
    id INTEGER PRIMARY KEY,
    date DATE,
    channel TEXT,
    sessions INTEGER,
    UNIQUE(date, channel)
);
```

### Redis Cache

```
Database: 1 (separato da memoria agent db=0)
Chiavi: ga4:metrics:YYYY-MM-DD
TTL: 14 giorni (sliding window)
Contenuto: JSON metriche giornaliere
```

---

## 🐛 Troubleshooting

### Redis non disponibile

```bash
# Verifica stato
redis-cli ping

# Avvia Redis
redis-server &

# Verifica processo
ps aux | grep redis
```

### Database non accessibile

```bash
# Verifica esistenza
ls -la data/ga4_data.db

# Ricrea se necessario
uv run scripts/setup_database.py

# Verifica statistiche
python -c "from ga4_extraction.database import GA4Database; db = GA4Database(); print(db.get_statistics()); db.close()"
```

### Tool agente non trovano dati

```bash
# Verifica record in database
python -c "from ga4_extraction.database import GA4Database; db = GA4Database(); print(f'Record: {db.get_record_count()}'); db.close()"

# Popola database se vuoto
uv run scripts/backfill_missing_dates.py --start-date 2025-10-01
```

### Memoria Redis non caricata

```bash
# Ricarica memoria
uv run agent/load_memory.py

# Verifica chiavi
redis-cli KEYS "agent:memory:weborder:*"
```

---

## 🔧 Utility

```bash
# Pulizia file temporanei
./scripts/cleanup.sh

# Statistiche database
python -c "from ga4_extraction.database import GA4Database; db = GA4Database(); print(db.get_statistics()); db.close()"

# Info cache Redis
python -c "from ga4_extraction.redis_cache import GA4RedisCache; cache = GA4RedisCache(); print(cache.get_cache_info()); cache.close()"
```

---

## 📚 Configurazione

### `config.yaml`

```yaml
agent:
  model: "claude-sonnet-4-5-20250929"
  verbose: true

redis:
  host: "localhost"
  port: 6379
  db: 0
  memory_prefix: "agent:memory:weborder"

database:
  sqlite:
    path: "data/ga4_data.db"
  redis:
    host: "localhost"
    port: 6379
    db: 1
    key_prefix: "ga4:metrics:"
    ttl_days: 14

execution:
  output_dir: "email"
  draft_filename: "draft_email.md"
  archive_dir: "email/archive"
```

---

## 🔐 Sicurezza

- ⚠️ **NON committare** `.env` con API keys
- ⚠️ **NON committare** `credentials/token.json`
- ✅ `.gitignore` configurato per file sensibili
- ✅ Redis locale senza autenticazione (solo sviluppo)

---

## 📊 Log Files

Tutti i log sono centralizzati in `logs/`:

- `logs/setup_database.log` - Setup database
- `logs/backfill_missing_dates.log` - Backfill dati
- `logs/extract_channels_delayed.log` - Estrazione canali
- `agent_execution.log` - Esecuzione agent (root)

---

## 🎯 Principi Architetturali

### SOLID

- **Single Responsibility**: Ogni modulo ha una responsabilità specifica
- **Open/Closed**: Estensibile via factory e service layer
- **Dependency Inversion**: Context managers e dependency injection

### DRY

- Service layer elimina duplicazione codice
- Factory centralizza creazione risorse
- Context managers gestiscono lifecycle

### KISS

- Struttura directory intuitiva
- Separazione script/test/core
- Nomi file descrittivi

---

## 📚 Risorse

- [datapizza-ai Documentation](https://github.com/datapizza-labs/datapizza-ai)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [Redis Documentation](https://redis.io/docs/)
- [GA4 Data API](https://developers.google.com/analytics/devguides/reporting/data/v1)

---

## 🆘 Support

Per problemi:
1. Verifica Redis: `redis-cli ping`
2. Verifica logs: `tail -f logs/*.log`
3. Test integrazione: `uv run tests/test_integration.py`
4. Ricarica memoria: `uv run agent/load_memory.py`

---

**Version:** 3.0.0 (SOLID Architecture)  
**Last Updated:** 2025-11-11  
**Framework:** datapizza-ai 0.0.7+

## 🎯 Changelog v3.0.0

### ✨ Nuove Funzionalità

- **SOLID Architecture**: Factory pattern, service layer, dependency injection
- **Struttura Riorganizzata**: `scripts/`, `tests/`, `logs/` directories
- **Service Layer**: `GA4DataService` per business logic centralizzata
- **Factory Pattern**: `GA4ResourceFactory` per gestione risorse
- **Context Managers**: Gestione automatica lifecycle risorse
- **Data Existence Check**: Skip estrazione se dati già presenti

### 🗂️ Riorganizzazione

- ✅ Script utility → `scripts/`
- ✅ Test consolidati → `tests/`
- ✅ Log centralizzati → `logs/`
- ✅ File obsoleti rimossi
- ✅ `.gitignore` aggiornato

### 🔧 Breaking Changes

- ⚠️ Path script cambiati: `uv run scripts/setup_database.py`
- ⚠️ Path test cambiati: `uv run tests/test_integration.py`
- ⚠️ Import aggiornati per nuova struttura

### 📈 Performance

- Check esistenza dati: ~5ms (skip estrazione duplicata)
- Service layer: -30% duplicazione codice
- Context managers: gestione risorse automatica

---

**Made with ❤️ using datapizza-ai**
