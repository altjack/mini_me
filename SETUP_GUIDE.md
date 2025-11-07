# 🚀 Guida Setup Rapido - Daily Report Agent

## ✅ Completamento Implementazione

**Status**: ✅ Implementazione completata con successo (30/30 test passati)

Tutti i componenti sono stati implementati e testati:
- ✅ Sistema memoria Redis
- ✅ Integrazione datapizza-ai
- ✅ Tool per lettura CSV
- ✅ Agent con memoria storica
- ✅ Workflow approvazione
- ✅ Configurazione YAML

---

## 📋 Prossimi Passi

### 1️⃣ Installazione Redis

```bash
# macOS
brew install redis

# Linux (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install redis-server

# Verifica installazione
redis-server --version
```

### 2️⃣ Avvio Redis

```bash
# Opzione 1: Background
redis-server --daemonize yes

# Opzione 2: Terminale dedicato
redis-server

# Verifica funzionamento
redis-cli ping
# Deve rispondere: PONG
```

### 3️⃣ Installazione Dipendenze Python

```bash
cd /Users/giacomomauri/Desktop/Automation/daily_report

# Con uv (consigliato)
uv sync

# Verifica installazione
uv run python -c "import redis, yaml; print('✓ Dipendenze OK')"
```

### 4️⃣ Caricamento Memoria Iniziale

```bash
# Carica la conversazione storica in Redis
uv run python agent/load_memory.py
```

**Output atteso:**
```
✓ Redis connesso e funzionante

✓ Memoria caricata con successo!
  - Conversazione: Weborder Residential Performance Update
  - Messaggi caricati: 12
  - Prefix Redis: agent:memory:weborder
```

### 5️⃣ Verifica Setup Completo

```bash
# Esegui test integrazione
uv run python test_integration.py
```

Deve mostrare: **✓ TUTTI I TEST SUPERATI! (30/30)**

---

## 🔄 Workflow Operativo

### Fase 1: Estrazione Dati GA4 (Automatica via Cron)

```bash
# Eseguito automaticamente ogni giorno
python main.py
```

Genera file CSV in `output/`:
- `sessioni_YYYYMMDD_HHMMSS.csv`
- `swi_YYYYMMDD_HHMMSS.csv`
- `cr_commodity_YYYYMMDD_HHMMSS.csv`
- `cr_canalizzazione_YYYYMMDD_HHMMSS.csv`
- `prodotti_YYYYMMDD_HHMMSS.csv`
- `report_completo_YYYYMMDD_HHMMSS.csv`

### Fase 2: Generazione Email (Manuale On-Demand)

```bash
# Genera draft email usando dati GA4 e memoria
uv run python run_agent.py
```

**Cosa fa:**
1. ✅ Verifica disponibilità dati GA4
2. 🧠 Carica memoria Redis (12 messaggi storici)
3. 🤖 Crea agente con contesto
4. 📧 Genera email professionale
5. 💾 Salva in `email/draft_email.md`

### Fase 3: Review Draft

```bash
# Visualizza il draft generato
cat email/draft_email.md

# Oppure apri con editor
code email/draft_email.md
```

### Fase 4: Approvazione e Memoria Incrementale

```bash
# Avvia workflow approvazione
uv run python approve_draft.py
```

**Opzioni:**
- **[y]** Approva → Aggiunge a Redis + Archivia
- **[n]** Rifiuta → Mantiene draft per modifiche
- **[v]** Visualizza di nuovo

**Se approvato:**
- ✅ Email aggiunta alla memoria Redis
- 📁 Archiviata in `email/archive/email_YYYYMMDD_HHMMSS.md`
- 🔄 Disponibile per futuri riferimenti

---

## 🎯 Esempio Completo

```bash
# SETUP (una tantum)
brew install redis
redis-server --daemonize yes
cd /Users/giacomomauri/Desktop/Automation/daily_report
uv sync
uv run python agent/load_memory.py

# WORKFLOW GIORNALIERO
# 1. Estrazione automatica (cron)
python main.py

# 2. Generazione email (manuale)
uv run python run_agent.py

# 3. Review
cat email/draft_email.md

# 4. Approvazione
uv run python approve_draft.py
# Premi 'y' per approvare
```

---

## 📊 Monitoraggio

### Verifica Stato Redis

```bash
# Verifica connessione
redis-cli ping

# Visualizza chiavi memoria
redis-cli KEYS "agent:memory:weborder:*"

# Conta messaggi in memoria
redis-cli GET "agent:memory:weborder:count"
```

### Statistiche Memoria

```python
# Script per visualizzare stats
python -c "
from agent.load_memory import get_memory_stats
import json
print(json.dumps(get_memory_stats(), indent=2))
"
```

### Log Files

- `ga4_extraction.log` - Log estrazione GA4
- `agent_execution.log` - Log esecuzione agente
- `memory_operations.log` - Log operazioni Redis

---

## ⚙️ Configurazione

### File `config.yaml`

Personalizza comportamento agente:

```yaml
agent:
  model: "claude-sonnet-4"    # Modello AI
  verbose: true                # Output dettagliato

execution:
  task_prompt: >
    [Personalizza prompt per l'agente...]
```

### Variabili Ambiente (`.env`)

```env
ANTHROPIC_API_KEY=your_api_key_here
```

---

## 🔧 Troubleshooting

### Redis non risponde

```bash
# Verifica processo
ps aux | grep redis

# Riavvia Redis
redis-cli shutdown
redis-server --daemonize yes

# Test connessione
redis-cli ping
```

### Memoria non caricata

```bash
# Ricarica memoria (attenzione: sovrascrive esistente)
uv run python agent/load_memory.py

# Verifica
redis-cli GET "agent:memory:weborder:count"
```

### Agent fallisce

```bash
# Verifica logs
tail -f agent_execution.log

# Test connessione API
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('API Key:', os.getenv('ANTHROPIC_API_KEY')[:10] + '...')
"
```

---

## 📁 Struttura File

```
daily_report/
├── agent/
│   ├── agent.py              ✅ Configurazione agente
│   ├── prompt.py             ✅ System prompt
│   ├── tools.py              ✅ Tool functions (+ read_latest_csv_report)
│   └── load_memory.py        ✅ Gestione memoria Redis
│
├── email/
│   ├── draft_email.md        📧 Draft corrente
│   └── archive/              📁 Email approvate
│
├── output/                   📊 CSV dati GA4
│
├── config.yaml               ⚙️ Configurazione
├── run_agent.py              🚀 Esecuzione agente
├── approve_draft.py          ✅ Workflow approvazione
├── test_integration.py       🧪 Test sistema
│
└── conversation_weborder.json 🧠 Conversazione storica
```

---

## 🎓 Best Practices

### 1. Backup Memoria Redis

```bash
# Backup manuale
redis-cli SAVE
cp /var/lib/redis/dump.rdb ~/backup/redis_backup_$(date +%Y%m%d).rdb
```

### 2. Monitoraggio Qualità Email

Dopo ogni approvazione, verifica:
- ✅ Tono professionale mantenuto
- ✅ Metriche chiave presenti (SWI, CR, sessioni)
- ✅ Confronti percentuali corretti
- ✅ Focus su weborder_residenziale

### 3. Manutenzione Archivio

```bash
# Conta email archiviate
ls -1 email/archive/*.md | wc -l

# Ultimi 5 archivi
ls -t email/archive/*.md | head -5
```

---

## 📞 Supporto

### Comandi Utili

```bash
# Test completo sistema
uv run python test_integration.py

# Verifica configurazione
python -c "import yaml; print(yaml.safe_load(open('config.yaml')))"

# Reset memoria (ATTENZIONE: cancella tutto)
redis-cli FLUSHDB

# Ricarica memoria iniziale
uv run python agent/load_memory.py
```

### File di Riferimento

- **README.md** - Documentazione completa
- **email/README.md** - Workflow email
- **SETUP_GUIDE.md** - Questa guida

---

## ✨ Sistema Pronto!

Il tuo agente AI è completamente configurato e testato. 

**Inizia subito:**
```bash
uv run python run_agent.py
```

Buon lavoro! 🚀

