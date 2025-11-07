# Daily Report GA4 Agent

Sistema automatico per l'estrazione dati GA4 e generazione email giornaliere con AI Agent.

**🆕 NEW: Storage ibrido SQLite + Redis per eliminare proliferazione CSV**

## 📋 Architettura (Aggiornata)

```
┌─────────────┐
│  Cron Job   │  Esecuzione automatica giornaliera
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   main.py   │  Estrazione dati GA4
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
       │         ┌───────────────────────┘
       │         │
       ▼         ▼
┌─────────────────────┐
│  Agent Tools        │  Accesso ottimizzato
│  (read-through)     │  Redis → SQLite fallback
└──────┬──────────────┘
       │
       ▼ (manuale)
┌─────────────┐
│run_agent.py │  Genera draft email
└──────┬──────┘
       │
       ▼
┌─────────────┐
│draft_email  │  Email in attesa di review
└──────┬──────┘
       │
       ▼ (manuale)
┌─────────────┐
│approve_draft│  Approvazione
└──────┬──────┘
       │
       ▼
┌─────────────┐
│email/archive│  Email archiviate
└─────────────┘
```

### Vantaggi Nuova Architettura

- ✅ **Zero CSV**: Nessuna proliferazione di file in `output/`
- ✅ **Storico completo**: SQLite mantiene tutti i dati permanentemente
- ✅ **Performance**: Redis cache ultimi 14 giorni (ms instead of file parsing)
- ✅ **Flessibilità**: Comparison dinamici con qualsiasi periodo passato
- ✅ **Schema normalizzato**: Zero duplicazione dati

## 🚀 Setup Iniziale

### 1. Installazione Dipendenze

```bash
# Installa dipendenze Python
uv sync

# O con pip
pip install -r requirements.txt
```

### 2. Installazione Redis

```bash
# macOS
brew install redis

# Linux (Ubuntu/Debian)
sudo apt-get install redis-server

# Verifica installazione
redis-server --version
```

### 3. Avvio Redis

```bash
# Avvio in background
redis-server &

# Oppure usa un terminale dedicato
redis-server

# Verifica connessione
redis-cli ping
# Output atteso: PONG
```

### 4. Configurazione

Crea/verifica file `.env` con:
```env
ANTHROPIC_API_KEY=your_api_key_here
```

### 5. Setup Database

```bash
python setup_database.py
```

Questo script:
- Crea directory `data/` e `data/backups/`
- Inizializza schema SQLite (`daily_metrics`, `products_performance`)
- Verifica connessione Redis (opzionale)
- Configura TTL 14 giorni per cache

Output atteso:
```
✓ Directory creata
✓ Database connesso: data/ga4_data.db
✓ Schema creato con successo
✓ Redis connesso: localhost:6379 (db=1)
```

### 6. Backfill Storico (60 giorni)

```bash
python backfill_ga4.py
```

Questo script:
- Estrae ultimi 60 giorni di dati da GA4
- Popola SQLite con tutti i 60 giorni
- Popola Redis cache con ultimi 14 giorni
- Genera baseline solida per analisi trend

**IMPORTANTE**: Richiede 10-15 minuti e credenziali GA4 valide.

Output atteso:
```
[60/60] Estrazione 2025-11-02... ✓ OK (251 conv, 4 prod)
✓ Giorni estratti: 60/60
📊 Record totali in DB: 60
💾 Redis cache popolato: 14 giorni
```

## 📊 Workflow Giornaliero

### Step 1: Estrazione Dati GA4 (Automatico)

```bash
# Eseguito automaticamente dal cron
python main.py
```

Cosa fa:
- Estrae dati GA4 per ieri
- Salva in database SQLite (`data/ga4_data.db`)
- Aggiorna Redis cache (ultimi 14 giorni)
- **ZERO file CSV generati** (nuova architettura)

Output:
```
✓ Estrazione completata con successo
✓ Dati salvati in database per 2025-11-02
📊 Record totali: 61
```

### Step 2: Generazione Email (Manuale)

```bash
python run_agent.py
```

Questo script:
1. ✅ Verifica disponibilità dati GA4
2. 🧠 Carica memoria Redis
3. 🤖 Crea agente con contesto storico
4. 📧 Genera email professionale
5. 💾 Salva draft in `email/draft_email.md`

### Step 3: Review Draft

```bash
# Visualizza il draft generato
cat email/draft_email.md

# Oppure apri con editor
code email/draft_email.md
```

### Step 4: Approvazione

```bash
python approve_draft.py
```

Il script mostra il draft e chiede conferma:
- **[y] Approva**: Aggiunge a memoria Redis + archivia
- **[n] Rifiuta**: Mantiene draft per modifiche
- **[v] Visualizza**: Mostra di nuovo il contenuto

Se approvato:
- ✅ Draft aggiunto alla memoria Redis
- 📁 Archiviato in `email/archive/email_YYYYMMDD_HHMMSS.md`
- 🗑️ Draft rimosso da `email/`

## 🔧 Configurazione

### File `config.yaml`

```yaml
agent:
  model: "claude-sonnet-4"      # Modello Anthropic
  verbose: true                  # Output dettagliato

redis:
  host: "localhost"
  port: 6379
  db: 0
  memory_prefix: "agent:memory:weborder"

execution:
  data_source: "output"          # Cartella CSV
  output_dir: "email"            # Cartella draft
  draft_filename: "draft_email.md"
  archive_dir: "email/archive"
  
  task_prompt: >
    Analizza i dati GA4 più recenti e genera email giornaliera
    professionale con focus su weborder_residenziale...
```

## 🛠️ Tools Agente (Aggiornati)

L'agente ha accesso ai seguenti tool con **accesso database ottimizzato**:

| Tool | Descrizione | Performance |
|------|-------------|-------------|
| `get_ga4_metrics(date, compare_days_ago)` | Metriche con comparison dinamico | 🚀 Redis cache |
| `get_metrics_trend(days, metric)` | Trend analysis ultimi N giorni | 🚀 Redis cache |
| `get_weekly_summary()` | Confronto settimana corrente vs precedente | 🚀 Redis cache |
| `read_latest_csv_report(type)` | **[LEGACY]** Legge CSV (fallback) | 🐌 File I/O |

### Nuovi Tool - Esempi

**get_ga4_metrics**: Comparison dinamico con qualsiasi periodo
```python
# Confronto con 7 giorni fa (default)
get_ga4_metrics(date="2025-11-02")

# Confronto con 14 giorni fa
get_ga4_metrics(date="2025-11-02", compare_days_ago=14)
```

**get_metrics_trend**: Analisi trend multi-giorno
```python
# Trend SWI ultimi 7 giorni
get_metrics_trend(days=7, metric="swi_conversioni")

# Trend CR commodity ultimi 14 giorni
get_metrics_trend(days=14, metric="cr_commodity")
```

**get_weekly_summary**: Overview settimanale automatica
```python
# Media settimana corrente vs precedente
get_weekly_summary()  # Tutte le metriche
```

## 🧪 Test Estrazioni GA4

### Test con Credenziali Reali

Prima di integrare nuove query nel workflow, usa lo script di test:

```bash
# Test ieri (default)
python test_ga4_extraction_real.py

# Test data specifica
python test_ga4_extraction_real.py --date 2025-11-02
```

Il test verifica:
- ✅ **Connessione GA4**: Credenziali valide
- ✅ **Tipi dati**: int/float corretti per ogni metrica
- ✅ **Timeout**: Warning se >30s
- ✅ **Valori validi**: Fallisce se null/0 (dove richiesto)
- ✅ **Print dettagliato**: Tutti i risultati estratti

**IMPORTANTE**: Questo test NON salva dati in database - serve solo per validazione query.

Output esempio:
```
✓ OK   date_range_0 (corrente): 251 (tipo: int)
✓ OK   date_range_1 (precedente): 123 (tipo: int)
✓ OK   change (%): 104.07 (tipo: float)
⏱️  Tempo esecuzione: 2.34s
```

## 📝 Database

### Schema SQLite (Normalizzato)

```sql
-- Metriche giornaliere (1 record per giorno)
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
```

### Redis Cache

```
Chiavi: ga4:metrics:YYYY-MM-DD
TTL: 14 giorni (sliding window)
Database: 1 (separato da memoria agente che usa db=0)
Contenuto: JSON metriche giornaliere
```

### Memoria Redis Agente

```
agent:memory:weborder:messages  -> Lista messaggi JSON (db=0)
agent:memory:weborder:metadata  -> Info conversazione (db=0)
agent:memory:weborder:count     -> Contatore messaggi (db=0)
```

### Gestione Memoria

```bash
# Visualizza statistiche
python -c "from agent.load_memory import get_memory_stats; print(get_memory_stats())"

# Ricarica memoria (ATTENZIONE: cancella memoria esistente)
python agent/load_memory.py

# Verifica connessione Redis
redis-cli ping
```

## 🐛 Troubleshooting

### Redis non disponibile

```bash
# Verifica stato Redis
redis-cli ping

# Se non risponde, avvia Redis
redis-server &

# Verifica processo
ps aux | grep redis
```

### Errore "ANTHROPIC_API_KEY non trovata"

```bash
# Verifica .env
cat .env | grep ANTHROPIC_API_KEY

# Oppure esporta manualmente
export ANTHROPIC_API_KEY="your_key_here"
```

### Memoria non caricata

```bash
# Ricarica memoria
python agent/load_memory.py

# Verifica chiavi Redis
redis-cli KEYS "agent:memory:weborder:*"
```

### Draft non trovato

```bash
# Verifica che run_agent.py sia stato eseguito
ls -la email/draft_email.md

# Rigenera draft
python run_agent.py
```

## 📦 Struttura Progetto (Aggiornata)

```
daily_report/
├── agent/
│   ├── agent.py              # Configurazione agente
│   ├── prompt.py             # System prompt
│   ├── tools.py              # Tool functions (+ nuovi tool DB)
│   └── load_memory.py        # Gestione memoria Redis
├── ga4_extraction/
│   ├── extraction.py         # Logica estrazione GA4 (+ save_to_database)
│   ├── config.py             # Configurazione GA4
│   ├── filters.py            # Filtri query
│   ├── database.py           # 🆕 SQLite manager
│   └── redis_cache.py        # 🆕 Redis cache manager
├── data/                     # 🆕 Database SQLite
│   ├── ga4_data.db           # 🆕 Database principale
│   └── backups/              # 🆕 Backup automatici
├── email/
│   ├── draft_email.md        # Draft corrente
│   └── archive/              # Email approvate
├── output/                   # CSV legacy (empty con nuova arch)
├── config.yaml               # Configurazione (+ sezione database)
├── main.py                   # Orchestrator (+ integrazione DB)
├── run_agent.py              # Esecuzione agente
├── approve_draft.py          # Workflow approvazione
├── setup_database.py         # 🆕 Setup schema database
├── backfill_ga4.py           # 🆕 Backfill 60 giorni
├── test_ga4_extraction_real.py # 🆕 Test estrazioni reali
├── conversation_weborder.json # Conversazione storica
└── pyproject.toml            # Dipendenze
```

## 🔄 Workflow Completo (Esempio Aggiornato)

```bash
# 1. Setup iniziale (una tantum)
brew install redis
redis-server &

# 2. Setup database
python setup_database.py

# 3. Backfill storico 60 giorni
python backfill_ga4.py
# ⏱️ Richiede ~10-15 minuti

# 4. Test estrazione (opzionale)
python test_ga4_extraction_real.py

# 5. Estrazione dati (cron giornaliero)
python main.py

# 6. Generazione email (manuale)
python run_agent.py

# 7. Review
cat email/draft_email.md

# 8. Approvazione
python approve_draft.py
# [y] per approvare
```

## 🐛 Troubleshooting (Aggiornato)

### Database non accessibile

```bash
# Verifica esistenza database
ls -la data/ga4_data.db

# Se non esiste, esegui setup
python setup_database.py

# Verifica statistiche
python -c "from ga4_extraction.database import GA4Database; db = GA4Database(); print(db.get_statistics()); db.close()"
```

### Redis cache non funziona

```bash
# Verifica Redis
redis-cli -h localhost -p 6379 -n 1 ping
# Output atteso: PONG

# Se non risponde, avvia Redis
redis-server &

# Verifica chiavi cache
redis-cli -h localhost -p 6379 -n 1 KEYS "ga4:metrics:*"
```

### Tool agente non trovano dati

```bash
# Verifica record in database
python -c "from ga4_extraction.database import GA4Database; db = GA4Database(); print(f'Record: {db.get_record_count()}'); db.close()"

# Se 0 record, esegui backfill
python backfill_ga4.py

# Verifica cache Redis
python -c "from ga4_extraction.redis_cache import GA4RedisCache; cache = GA4RedisCache(); info = cache.get_cache_info(); print(f'Cache: {info}'); cache.close()"
```

### Backfill timeout o errori

```bash
# Test singola estrazione prima di backfill completo
python test_ga4_extraction_real.py --date 2025-11-02

# Se fallisce, verifica:
# 1. Credenziali GA4 valide
cat credentials/token.json

# 2. Property ID corretto
grep PROPERTY_ID ga4_extraction/extraction.py

# 3. Connessione API Google
curl -I https://analyticsdata.googleapis.com
```

### Dati duplicati o inconsistenti

```bash
# Elimina database e ricrea
rm data/ga4_data.db
python setup_database.py
python backfill_ga4.py

# Pulisci cache Redis
redis-cli -h localhost -p 6379 -n 1 FLUSHDB
```

## 📊 Log Files

- `ga4_extraction.log` - Log estrazione GA4
- `agent_execution.log` - Log esecuzione agente
- `memory_operations.log` - Log operazioni Redis

## 🔐 Sicurezza

- ⚠️ **NON committare** `.env` con API keys
- ⚠️ **NON committare** `credentials/token.json` (GA4)
- ✅ Usa `.gitignore` per file sensibili
- ✅ Redis locale senza autenticazione (solo sviluppo)

## 📚 Risorse

- [datapizza-ai Documentation](https://github.com/datapizza-labs/datapizza-ai)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [Redis Documentation](https://redis.io/docs/)
- [GA4 Data API](https://developers.google.com/analytics/devguides/reporting/data/v1)

## 🆘 Support

Per problemi o domande:
1. Verifica Redis: `redis-cli ping`
2. Verifica logs: `tail -f agent_execution.log`
3. Test connessione: `python agent/agent.py`
4. Ricarica memoria: `python agent/load_memory.py`

---

**Version:** 2.0.0 (Database Architecture)  
**Last Updated:** 2025-11-03  
**Framework:** datapizza-ai 0.0.7+

## 🎯 Changelog v2.0.0

### ✨ Nuove Funzionalità

- **Storage Ibrido SQLite + Redis**: Zero CSV files, storage permanente + cache veloce
- **Schema Normalizzato**: Ogni giorno = 1 record unico, zero duplicazioni
- **Comparison Dinamici**: Confronto con qualsiasi periodo passato al volo
- **Backfill Tool**: Popola database con 60 giorni di storico iniziale
- **Test Tool**: Valida estrazioni GA4 prima di integrazione
- **Nuovi Tool Agente**: `get_ga4_metrics()`, `get_metrics_trend()`, `get_weekly_summary()`

### 🔧 Modifiche Breaking

- ⚠️ **CSV Generation Deprecata**: `output/` non genera più CSV multipli
- ⚠️ **Setup Richiesto**: Prima esecuzione richiede `setup_database.py` + `backfill_ga4.py`
- ⚠️ **Config Aggiornato**: Nuova sezione `database` in `config.yaml`

### 📈 Performance

- Redis cache: ~10-50ms per letture ultimi 14 giorni
- SQLite fallback: ~50-100ms per query storico completo
- Backfill iniziale: ~10-15 minuti per 60 giorni

### 🔄 Migrazione da v1.0.0

1. Backup CSV esistenti: `mv output output_backup`
2. Setup database: `python setup_database.py`
3. Backfill storico: `python backfill_ga4.py`
4. Test: `python test_ga4_extraction_real.py`
5. Workflow normale: `python main.py`

