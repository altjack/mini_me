# Piano: Fix UI e Persistenza Stato

## Obiettivi
1. **Linea Cambio Campagna**: Modificare da rossa tratteggiata a nera continua (linea + etichetta)
2. **Stato Confronto Promozioni**: Persistere lo stato del confronto quando si cambia pagina
3. **Backfill in Background**: Permettere al processo di continuare anche cambiando pagina

---

## 1. Linea Cambio Campagna - Nera e Continua

**File da modificare**: `src/components/Dashboard.jsx`

**Modifiche** (linee 526-542):
- Cambiare `stroke` da `CAMPAIGN_COLOR` (#dc2626) a `#000000` (nero)
- Rimuovere `strokeDasharray="4 2"` per renderla continua
- Cambiare `fill` dell'etichetta da `CAMPAIGN_COLOR` a `#000000`

**Opzione**: Definire una nuova costante `CAMPAIGN_LINE_COLOR = '#000000'` per chiarezza

---

## 2. Persistenza Stato Confronto Promozioni

**Problema attuale**: Lo stato del confronto (selectedPromo, compStartDate, compEndDate) è locale a PromoDashboard e si perde al cambio pagina.

**Soluzione**: Creare un Context per lo stato delle promozioni

**File da creare/modificare**:

### A. Nuovo file: `src/context/PromoContext.jsx`
- Creare un context che gestisce:
  - `selectedPromo`
  - `compStartDate`
  - `compEndDate`
- Provider che avvolge l'app

### B. Modificare: `src/App.jsx`
- Importare e aggiungere `PromoProvider` nel tree dei provider

### C. Modificare: `src/components/PromoDashboard.jsx`
- Sostituire useState locali con useContext(PromoContext)
- Mantenere la logica esistente per il fetch dei dati

---

## 3. Backfill in Background

**Problema attuale**: Il backfill è sincrono e bloccante. Se l'utente cambia pagina, perde lo stato.

**Soluzione**: Creare un sistema di gestione del backfill con stato globale

**File da creare/modificare**:

### A. Nuovo file: `src/context/BackfillContext.jsx`
- Stato globale per:
  - `isRunning` (boolean)
  - `progress` (null | { current, total, currentDate })
  - `result` (null | { success, message, details })
  - `error` (null | string)
- Funzione `startBackfill(params)` che:
  1. Imposta `isRunning = true`
  2. Esegue la chiamata API
  3. Aggiorna `result` o `error` al completamento
  4. Imposta `isRunning = false`

### B. Modificare: `src/App.jsx`
- Aggiungere `BackfillProvider` nel tree dei provider

### C. Modificare: `src/components/BackfillPanel.jsx`
- Usare `useContext(BackfillContext)` invece di useState locali
- Mostrare lo stato corrente quando il componente viene montato
- Disabilitare il form se un backfill è già in corso
- Mostrare risultato/errore dell'ultimo backfill

---

## Sequenza di Implementazione

1. **[Rapido]** Modificare stile linea cambio campagna in Dashboard.jsx
2. **[Medio]** Creare PromoContext e integrarlo
3. **[Medio]** Creare BackfillContext e integrarlo

---

## Note Tecniche

- I Context sono la soluzione standard React per stato condiviso tra componenti
- Non serve persistenza su localStorage perché:
  - Il confronto promozioni è una selezione temporanea di sessione
  - Il backfill è un processo una tantum
- Se il browser viene ricaricato, lo stato si resetta (comportamento accettabile)
