# 📚 Guida Completa: Tool Agent e Flusso Generazione Email

## 🎯 Panoramica del Sistema

L'agente AI genera email giornaliere analizzando dati GA4. Il processo segue questo flusso:

```
┌─────────────────┐
│  run_agent.py   │  Avvia workflow
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Agent Setup    │  Carica esempi + tools
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Task Prompt    │  "GENERA EMAIL COMPLETA..."
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Agent.run()    │  Esecuzione iterativa
└────────┬────────┘
         │
         ├───► Tool Call 1 ──┐
         │                    │
         ├───► Tool Call 2 ──┤
         │                    ├──► Database SQLite/Redis
         ├───► Tool Call 3 ──┤
         │                    │
         └───► Tool Call N ───┘
         │
         ▼
┌─────────────────┐
│  Email Output   │  Email completa in markdown
└─────────────────┘
```

---

## 🔧 Tool Disponibili (Dettaglio)

### 1. `get_daily_report(date: str)` ✅ **PRINCIPALE**

**Scopo**: Report completo per una data specifica con tutti i dettagli

**Fonte Dati**: Database SQLite (con fallback Redis)

**Cosa Restituisce**:
- Metriche giornaliere (sessioni commodity/lucegas, SWI, CR)
- Confronto dinamico con 7 giorni prima (calcolato dal DB)
- Performance prodotti (lista completa)
- Sessioni per canale (tutti i canali)

**Quando Usarlo**:
- Quando serve un report completo per una data specifica
- Quando servono tutti i dettagli (prodotti + canali)

**Esempio Output**:
```markdown
# Report Giornaliero GA4 - 2025-11-05
Confrontato con: 2025-10-29

## Sessioni
**Commodity:** 51,262 (+42.7%)
**Luce&Gas:** 26,827 (+9.8%)

## Conversioni
**SWI:** 200 (-15.2%)

## Performance Prodotti
- Fixa: 154 conversioni (77.00%)
- Trend: 25 conversioni (12.50%)
...

## Sessioni per Canale
- Paid Media e Display: 28,319 commodity, 7,993 luce&gas
- Paid Search: 15,337 commodity, 13,509 luce&gas
...
```

**Integrazione**: Tool principale per ottenere dati completi. L'agente lo usa quando ha bisogno di tutti i dettagli.

---

### 2. `get_metrics_summary(period_days: int = 1)` ✅ **ALTERNATIVO**

**Scopo**: Summary rapido degli ultimi N giorni

**Fonte Dati**: Database SQLite

**Cosa Restituisce**:
- Metriche per l'ultimo giorno disponibile (ieri - 1)
- Confronto con 7 giorni prima
- Top 10 canali (non tutti)
- Prodotti principali

**Quando Usarlo**:
- Quando serve un riepilogo veloce
- Quando non servono tutti i dettagli dei canali

**Differenza con `get_daily_report`**:
- Più veloce (meno dati)
- Limita a top 10 canali
- Calcola automaticamente "ieri - 1" per dati processati

**Integrazione**: Tool alternativo più leggero. L'agente può usarlo se `get_daily_report` non è disponibile o per un primo sguardo.

---

### 3. `get_product_performance(date: str)` ✅ **SPECIALIZZATO**

**Scopo**: Focus solo sui prodotti

**Fonte Dati**: Database SQLite

**Cosa Restituisce**:
- Solo performance prodotti per data specifica
- Nessuna altra metrica

**Quando Usarlo**:
- Quando serve solo l'analisi prodotti
- Come supplemento ad altri tool

**Integrazione**: Tool di supporto. L'agente lo usa se ha già le metriche principali ma vuole approfondire i prodotti.

---

### 4. `get_ga4_metrics(date: str = None, compare_days_ago: int = 7)` ✅ **OTTIMIZZATO**

**Scopo**: Metriche con cache Redis per performance

**Fonte Dati**: Redis cache (fallback SQLite)

**Cosa Restituisce**:
- Metriche giornaliere
- Confronto configurabile (default: 7 giorni)
- Prodotti
- **NON include sessioni per canale**

**Quando Usarlo**:
- Quando serve velocità (usa Redis cache)
- Quando non servono i dettagli dei canali
- Per confronti dinamici configurabili

**Performance**: ⚡ Più veloce grazie a Redis cache

**Integrazione**: Tool ottimizzato per performance. L'agente lo usa quando ha bisogno di dati veloci senza tutti i dettagli.

---

### 5. `get_metrics_trend(days: int = 7, metric: str = "swi_conversioni")` ✅ **ANALISI**

**Scopo**: Analisi trend per una metrica specifica

**Fonte Dati**: Database SQLite

**Cosa Restituisce**:
- Statistiche (media, min, max)
- Crescita percentuale (primo vs ultimo giorno)
- Valori giornalieri con deviazioni dalla media

**Quando Usarlo**:
- Per analisi approfondite di trend
- Per identificare pattern temporali
- Per analisi specifiche di una metrica

**Integrazione**: Tool di analisi avanzata. L'agente lo usa quando ha bisogno di analisi trend dettagliate.

---

### 6. `get_weekly_summary()` ✅ **SETTIMANALE**

**Scopo**: Confronto settimana corrente vs precedente

**Fonte Dati**: Database SQLite

**Cosa Restituisce**:
- Medie settimanali per tutte le metriche
- Confronto settimana corrente vs precedente
- Variazioni percentuali

**Quando Usarlo**:
- Per analisi settimanali
- Per report di sintesi

**Integrazione**: Tool per analisi settimanali. L'agente lo usa quando serve un contesto più ampio.

---

### 7. `read_latest_csv_report(report_type: str = "all")` ⚠️ **LEGACY**

**Scopo**: Legge file CSV dalla cartella `output/`

**Fonte Dati**: File CSV (legacy)

**Problema**: 
- ❌ I CSV non vengono più generati (nuova architettura usa solo DB)
- ⚠️ Tool deprecato ma ancora disponibile

**Quando Usarlo**: 
- ❌ Non dovrebbe essere usato
- ⚠️ Solo per retrocompatibilità

**Integrazione**: Tool legacy. **Il prompt attuale suggerisce di usarlo ma è obsoleto**. Va aggiornato.

---

### 8. `compare_periods(...)` ❌ **NON FUNZIONANTE**

**Scopo**: Confronto tra due periodi arbitrari

**Problema**: 
- ❌ Usa ancora formato vecchio (`date_range_0`, `date_range_1`)
- ❌ Chiama `esegui_giornaliero()` invece del database
- ❌ Non funziona correttamente

**Stato**: Necessita aggiornamento completo

---

## 🔄 Flusso Generazione Email (Attuale)

### Step 1: Setup Agente (`agent.py`)

```python
# 1. Carica esempi email da history.md (6 esempi recenti)
examples = load_examples("history.md")
selected = sample_examples(examples, n=6, strategy="recent_weighted")

# 2. Crea system prompt con esempi
enhanced_prompt = SYSTEM_PROMPT + examples_context

# 3. Registra tools disponibili
tools = [
    get_daily_report,
    get_metrics_summary,
    get_product_performance,
    compare_periods,
    read_latest_csv_report
]

# 4. Crea agent
agent = Agent(
    name="DailyReportAgent",
    system_prompt=enhanced_prompt,
    tools=tools
)
```

### Step 2: Task Prompt (`config.yaml`)

```yaml
task_prompt: >
  GENERA UN'EMAIL COMPLETA E PROFESSIONALE con i dati GA4 più recenti.
  
  STEP DA SEGUIRE:
  1. Usa il tool read_latest_csv_report("all") per ottenere i dati  # ⚠️ OBSOLETO
  2. Analizza le metriche chiave
  3. SCRIVI L'EMAIL COMPLETA
```

**⚠️ PROBLEMA**: Il prompt suggerisce `read_latest_csv_report` che è obsoleto!

### Step 3: Esecuzione Agente (`run_agent.py`)

```python
# Esegue agent.run(task_prompt)
result = agent.run(task_prompt)
```

L'agente decide autonomamente quali tool chiamare basandosi su:
- System prompt (istruzioni generali)
- Task prompt (richiesta specifica)
- Esempi email (few-shot learning)
- Contesto conversazione

### Step 4: Sequenza Tipica Tool Calls

**Sequenza Attuale (basata su prompt obsoleto)**:

```
1. read_latest_csv_report("all") 
   └─► ❌ Fallisce (CSV non esistono)
   
2. read_latest_csv_report("swi")
   └─► ❌ Fallisce
   
3. read_latest_csv_report("sessioni")
   └─► ❌ Fallisce
   
4. get_metrics_summary(period_days=1)
   └─► ✅ Successo (usa database)
   
5. get_daily_report(date="2025-11-05")
   └─► ✅ Successo (usa database)
   
6. Genera email completa
```

**Sequenza Ottimale (dovrebbe essere)**:

```
1. get_metrics_summary(period_days=1)
   └─► ✅ Ottiene overview rapido
   
2. get_daily_report(date="2025-11-05")  [se serve più dettaglio]
   └─► ✅ Ottiene tutti i dettagli (prodotti + canali)
   
3. get_product_performance(date="2025-11-05")  [opzionale]
   └─► ✅ Approfondimento prodotti se necessario
   
4. Genera email completa
```

---

## 📊 Decision Tree Agente

L'agente decide quali tool usare basandosi su:

```
┌─────────────────────────┐
│  Task: Genera Email     │
└────────────┬────────────┘
             │
             ▼
    ┌────────────────┐
    │ Serve overview? │
    └────┬───────┬────┘
         │       │
    SÌ   │       │ NO
         │       │
         ▼       ▼
┌─────────────┐ ┌──────────────────┐
│ get_metrics │ │ get_daily_report│
│ _summary()  │ │ (date)           │
└──────┬──────┘ └────────┬─────────┘
       │                  │
       └────────┬─────────┘
                │
                ▼
       ┌────────────────┐
       │ Serve dettaglio │
       │ prodotti?       │
       └────┬───────┬────┘
            │       │
       SÌ   │       │ NO
            │       │
            ▼       ▼
    ┌─────────────┐ ┌──────────────┐
    │ get_product │ │ Genera Email │
    │ _performance│ │              │
    └─────────────┘ └──────────────┘
```

---

## 🎯 Tool Consigliati per Email

### Per Email Standard (Raccomandato):

1. **`get_daily_report(date)`** - Tool principale
   - Include tutto: metriche, prodotti, canali
   - Confronto automatico con 7 giorni prima
   - Output completo e formattato

### Per Email Veloce:

1. **`get_metrics_summary(period_days=1)`**
   - Overview rapido
   - Top 10 canali (non tutti)
   - Più leggero

### Per Email con Analisi Trend:

1. **`get_metrics_summary()`** - Overview
2. **`get_metrics_trend(days=7, metric="swi_conversioni")`** - Trend SWI
3. **`get_metrics_trend(days=7, metric="cr_commodity")`** - Trend CR

---

## ⚠️ Problemi Attuali

### 1. Prompt Obsoleto

**Problema**: `config.yaml` suggerisce `read_latest_csv_report("all")` che non funziona più.

**Soluzione**: Aggiornare prompt per suggerire `get_metrics_summary()` o `get_daily_report()`.

### 2. Tool Legacy Disponibili

**Problema**: `read_latest_csv_report` e `compare_periods` sono ancora registrati ma non funzionano correttamente.

**Soluzione**: 
- Rimuovere `read_latest_csv_report` dai tool disponibili
- Aggiornare `compare_periods` per usare database

### 3. Tool Non Registrati

**Problema**: `get_ga4_metrics`, `get_metrics_trend`, `get_weekly_summary` esistono ma NON sono registrati in `agent.py`.

**Soluzione**: Aggiungere questi tool alla lista `available_tools`.

---

## 🔧 Raccomandazioni

### Tool da Registrare in `agent.py`:

```python
available_tools = [
    get_daily_report,        # ✅ Già presente
    get_metrics_summary,     # ✅ Già presente
    get_product_performance, # ✅ Già presente
    get_ga4_metrics,         # ➕ AGGIUNGERE (cache Redis)
    get_metrics_trend,       # ➕ AGGIUNGERE (analisi trend)
    get_weekly_summary,      # ➕ AGGIUNGERE (analisi settimanale)
    # compare_periods,       # ❌ Rimuovere finché non aggiornato
    # read_latest_csv_report # ❌ Rimuovere (deprecato)
]
```

### Prompt da Aggiornare (`config.yaml`):

```yaml
task_prompt: >
  GENERA UN'EMAIL COMPLETA E PROFESSIONALE con i dati GA4 più recenti.
  
  STEP DA SEGUIRE:
  1. Usa get_metrics_summary(period_days=1) per ottenere overview dati
  2. Se necessario, usa get_daily_report(date) per dettagli completi
  3. Analizza le metriche chiave (SWI, CR commodity, CR canalizzazione)
  4. SCRIVI L'EMAIL COMPLETA in italiano
```

---

## 📈 Metriche Prioritarie (Ordine)

Come indicato nel system prompt:

1. **SWI (Switch In)** - Conversioni totali + suddivisione per tipo (Fixa, Trend, Pernoi)
2. **CR Commodity** - Conversion Rate principale
3. **CR Canalizzazione** - Efficienza funnel
4. **Sessioni Commodity** - Traffico principale
5. **Sessioni Luce&Gas** - Traffico secondario
6. **Performance Prodotti** - Dettaglio prodotti specifici

---

## 🎨 Struttura Email Generata

Basata su esempi in `history.md`:

```
Oggetto: Weborder Residential Performance Update - [DATA]

Ciao [Nome],

[Apertura con trend principale]

**Metriche Chiave - [DATA]:**
- SWI: [valore] ([variazione]% vs periodo precedente)
  - Fixa: [valore] conversioni
  - Trend: [valore] conversioni
  - Pernoi: [valore] conversioni
- CR Commodity: [valore]% ([variazione]%)
- CR Canalizzazione: [valore]%
- Sessioni Commodity: [valore] ([variazione]%)
- Sessioni Luce&Gas: [valore] ([variazione]%)

[Analisi e commenti sui trend]

[Firma]
```

---

## 🔍 Debugging Tool Calls

Per vedere quali tool vengono chiamati:

1. **Log File**: `agent_execution.log`
2. **Verbose Mode**: `verbose=True` in `create_agent_with_memory()`
3. **Output Console**: L'agente mostra ogni tool call durante esecuzione

Esempio output:
```
<DailyReportAgent>
╭────────────────────── TOOL GET_METRICS_SUMMARY RESULT ───────────────────────╮
│ # Report Giornaliero GA4                                                      │
│ ## Data: 2025-11-05                                                          │
│ ...                                                                           │
╰──────────────────────────────────────────────────────────────────────────────╯
```

---

## 📝 Note Finali

- L'agente decide autonomamente quali tool chiamare
- La sequenza può variare in base al contesto
- Il system prompt guida le decisioni ma non le forza
- Gli esempi email influenzano lo stile e la struttura
- I tool aggiornati usano tutti il database SQLite/Redis

