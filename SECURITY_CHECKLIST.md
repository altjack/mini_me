# 🔐 Security Checklist - Daily Report

## ⚠️ AZIONE URGENTE: Revoca Credenziali Google OAuth

Il file `credentials/token.json` contiene credenziali Google OAuth sensibili che **devono essere revocate e rigenerate**.

### Passi da seguire:

#### 1. Revocare Token Esistenti
1. Vai su [Google Cloud Console](https://console.cloud.google.com/)
2. Seleziona il progetto associato
3. Vai su **APIs & Services** → **Credentials**
4. Trova l'OAuth 2.0 Client ID: `526957616102-prcgor97nrf0860gq5svjma5jqi78uce.apps.googleusercontent.com`
5. Clicca su **Reset Secret** per invalidare il client secret attuale

#### 2. Revocare Accesso Token
1. Vai su [Google Security Settings](https://myaccount.google.com/permissions)
2. Trova l'applicazione "Daily Report" (o nome simile)
3. Clicca **Remove Access** per revocare tutti i token attivi

#### 3. Rigenerare Credenziali
1. In Google Cloud Console, crea un **nuovo** OAuth 2.0 Client ID
2. Scarica il file JSON delle credenziali
3. **NON salvare** il file nel repository
4. Usa **environment variables** invece:

```bash
# Render/Vercel - aggiungi queste env vars
GOOGLE_CREDENTIALS_JSON='{"client_id":"...","client_secret":"...","type":"authorized_user"}'
```

#### 4. Eliminare File Locale
```bash
# Dopo aver configurato le env vars, elimina il file
rm credentials/token.json
```

---

## ✅ Vulnerabilità Corrette in Questo Commit

### 🔴 CRITICHE
- [x] **CORS Wildcard**: Rimosso `Access-Control-Allow-Origin: *` da `vercel.json`
  - Ora gestito dinamicamente dal codice Python con whitelist

### 🟠 ALTE
- [x] **Auth Bypass in Produzione**: Aggiunto fallback sicuro
  - Se `STAGING_USER`/`STAGING_PASSWORD` non configurati in produzione → errore 503
  - Solo in development locale si può saltare l'auth

- [x] **Information Disclosure**: Sanitizzati tutti i messaggi di errore
  - Errori interni loggati, ma mai esposti agli utenti
  - Nuova funzione `safe_error_response()` in `_utils.py`

### 🟡 MEDIE
- [x] **XSS via Markdown**: Aggiunto `rehype-sanitize` a ReactMarkdown
  - Previene esecuzione di script malevoli nel contenuto markdown

- [x] **Input Validation**: Migliorata validazione date
  - Nuova funzione `validate_date_string()` in `_utils.py`
  - Blocca date nel futuro e date troppo vecchie (< 2020)

### 🟢 BASSE
- [x] **Security Headers**: Aggiunti header di sicurezza in `vercel.json`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`

---

## 🔧 Configurazione Produzione Richiesta

Per il corretto funzionamento della sicurezza, configura queste **environment variables** su Vercel/Render:

```bash
# OBBLIGATORIE in produzione
STAGING_USER=<username>
STAGING_PASSWORD=<strong_password>
API_SECRET_KEY=<random_32_char_string>

# CORS - specifica le origini permesse (comma-separated)
CORS_ORIGINS=https://tuodominio.vercel.app,https://tuodominio.com

# Google OAuth (invece di file JSON)
GOOGLE_CREDENTIALS_JSON=<json_string>

# Database
DATABASE_URL=postgresql://...
```

### Generare API Secret Key
```bash
# Genera una chiave sicura
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 📋 Checklist Pre-Deploy

- [ ] Credenziali Google OAuth revocate e rigenerate
- [ ] `credentials/` directory vuota o rimossa
- [ ] Tutte le env vars configurate su Vercel
- [ ] CORS_ORIGINS contiene solo domini autorizzati
- [ ] Test manuale dell'autenticazione in preview
- [ ] Verificato che `/api/stats` richieda autenticazione

---

## 🧪 Test di Sicurezza Consigliati

```bash
# Test CORS - dovrebbe fallire da origine non autorizzata
curl -H "Origin: https://evil.com" \
     -I https://tuo-sito.vercel.app/api/stats

# Test auth bypass - dovrebbe ritornare 401
curl https://tuo-sito.vercel.app/api/stats

# Test error disclosure - non dovrebbe mostrare stack trace
curl -X POST https://tuo-sito.vercel.app/api/backfill \
     -H "Content-Type: application/json" \
     -d '{"start_date": "invalid"}'
```

