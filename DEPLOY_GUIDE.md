# Guida Deploy su Render - Daily Report

Questa guida ti accompagna passo-passo nel deploy dell'applicazione su Render.

## Prerequisiti

- Account GitHub con il repository pushato
- Credenziali Google Analytics (file `credentials/token.json`)
- API Key Anthropic

---

## Step 1: Crea Account Render

1. Vai su [render.com](https://render.com)
2. Clicca **Get Started for Free**
3. Scegli **Sign up with GitHub**
4. Autorizza Render ad accedere ai tuoi repository

---

## Step 2: Push Modifiche su GitHub

Prima di procedere con Render, assicurati che tutte le modifiche siano su GitHub:

```bash
cd /Users/giacomomauri/Desktop/Automation/daily_report

# Verifica stato
git status

# Aggiungi tutti i file modificati
git add .

# Commit
git commit -m "feat: configurazione per deploy Render

- Aggiunto requirements.txt per Render
- Modificato database.py per supporto PostgreSQL
- Aggiunto Basic Auth per protezione staging
- Creato render.yaml (Blueprint)
- Script migrazione dati"

# Push
git push origin main
```

---

## Step 3: Crea Database PostgreSQL

1. Dalla Dashboard Render, clicca **New +** → **PostgreSQL**
2. Configura:
   - **Name**: `daily-report-db`
   - **Database**: `daily_report`
   - **User**: lascia il default
   - **Region**: `Frankfurt (EU Central)` (per latenza EU)
   - **Plan**: `Free`
3. Clicca **Create Database**
4. **IMPORTANTE**: Copia la **Internal Database URL** (la userai dopo)
   - La trovi nella sezione "Connections" del database

---

## Step 4: Deploy Backend (Web Service)

1. Dashboard Render → **New +** → **Web Service**
2. Clicca **Connect a repository** e seleziona il tuo repo `daily_report`
3. Configura:
   - **Name**: `daily-report-api`
   - **Region**: `Frankfurt (EU Central)`
   - **Branch**: `main`
   - **Root Directory**: lascia vuoto (usa root)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn api:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
   - **Plan**: `Free`

4. Scorri fino a **Environment Variables** e aggiungi:

   | Key | Value | Note |
   |-----|-------|------|
   | `DATABASE_URL` | (incolla Internal Database URL) | Dal database creato |
   | `STAGING_USER` | `admin` | Username per accesso staging |
   | `STAGING_PASSWORD` | `TuaPasswordSicura123!` | Password complessa |
   | `ANTHROPIC_API_KEY` | `sk-ant-...` | La tua API key Anthropic |
   | `CORS_ORIGINS` | (lascia vuoto per ora) | Lo aggiornerai dopo |

5. **Google Credentials**: Per le credenziali Google Analytics:
   - Apri il file `credentials/token.json` locale
   - Copia l'intero contenuto JSON
   - Aggiungi variabile: `GOOGLE_CREDENTIALS_JSON` con il contenuto

6. Clicca **Create Web Service**
7. Attendi il deploy (5-10 minuti)
8. **Copia l'URL** del servizio (es. `https://daily-report-api.onrender.com`)

---

## Step 5: Deploy Frontend (Static Site)

1. Dashboard Render → **New +** → **Static Site**
2. Seleziona lo stesso repository
3. Configura:
   - **Name**: `daily-report-frontend`
   - **Branch**: `main`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `dist`

4. **Environment Variables**:

   | Key | Value |
   |-----|-------|
   | `VITE_API_URL` | `https://daily-report-api.onrender.com/api` |
   | `VITE_STAGING_USER` | `admin` (stesso del backend) |
   | `VITE_STAGING_PASSWORD` | `TuaPasswordSicura123!` (stesso del backend) |

5. Clicca **Create Static Site**
6. Attendi il deploy (2-3 minuti)
7. **Copia l'URL** del frontend (es. `https://daily-report-frontend.onrender.com`)

---

## Step 6: Aggiorna CORS Backend

Ora che hai l'URL del frontend, aggiorna le origini CORS:

1. Vai al servizio `daily-report-api` su Render
2. Sezione **Environment** → **Environment Variables**
3. Aggiungi/modifica:
   - `CORS_ORIGINS`: `https://daily-report-frontend.onrender.com`
4. Il servizio si riavvierà automaticamente

---

## Step 7: Migra i Dati

Ora devi migrare i dati dal tuo SQLite locale al PostgreSQL su Render.

### 7.1 Export Dati Locali

```bash
cd /Users/giacomomauri/Desktop/Automation/daily_report

# Export dati in JSON
python scripts/migrate_to_postgres.py export
```

Questo crea file JSON in `data/export/`.

### 7.2 Import su PostgreSQL

Per importare su Render, hai due opzioni:

**Opzione A: Usa Render Shell (più semplice)**

1. Vai al servizio `daily-report-api` su Render
2. Clicca **Shell** (nella sidebar)
3. Esegui:
```bash
python scripts/migrate_to_postgres.py import
```

**Opzione B: Da locale con DATABASE_URL**

1. Copia l'**External Database URL** dal database Render
2. Esegui:
```bash
DATABASE_URL="postgres://user:pass@host/db" python scripts/migrate_to_postgres.py import
```

### 7.3 Verifica

```bash
DATABASE_URL="..." python scripts/migrate_to_postgres.py verify
```

---

## Step 8: Test Applicazione

1. Apri il frontend: `https://daily-report-frontend.onrender.com`
2. Inserisci username e password quando richiesto
3. Verifica che:
   - La dashboard carichi i dati
   - I grafici mostrino le metriche
   - Il generatore email funzioni

---

## Troubleshooting

### Il backend non si avvia

1. Controlla i **Logs** su Render (sidebar del servizio)
2. Verifica che `DATABASE_URL` sia corretta
3. Verifica che tutte le env vars siano configurate

### Errore CORS

1. Verifica che `CORS_ORIGINS` contenga l'URL esatto del frontend
2. L'URL deve essere senza slash finale
3. Deve includere `https://`

### Il frontend non si connette al backend

1. Verifica `VITE_API_URL` nel frontend
2. L'URL deve terminare con `/api`
3. Verifica che username/password siano uguali in frontend e backend

### Database vuoto

1. Esegui lo script di migrazione
2. Verifica con `migrate_to_postgres.py verify`

### Sleep del servizio (tier gratuito)

Il servizio backend va in "sleep" dopo 15 minuti di inattività.
- La prima richiesta dopo lo sleep può richiedere ~30 secondi
- Questo è normale per il tier gratuito

---

## Costi

Con il tier gratuito di Render:
- **Backend**: $0/mese (con limitazioni sleep)
- **Frontend**: $0/mese (static site)
- **PostgreSQL**: $0/mese (256MB storage)

Per servizio sempre attivo: $7/mese per il backend.

---

## Prossimi Passi (Opzionali)

1. **Custom Domain**: Puoi collegare un tuo dominio al frontend
2. **Upgrade Piano**: Per evitare lo sleep del backend
3. **CI/CD**: I deploy sono già automatici ad ogni push su main

