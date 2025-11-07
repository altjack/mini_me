# Email Directory

Questa directory contiene gli output dell'agente per la generazione di email giornaliere.

## Struttura

```
email/
├── draft_email.md          # Draft corrente in attesa di approvazione
├── archive/                # Email approvate archiviate
│   └── email_YYYYMMDD_HHMMSS.md
└── README.md               # Questa documentazione
```

## Workflow

### 1. Generazione Draft
```bash
python run_agent.py
```
Genera `draft_email.md` basato sui dati GA4 più recenti.

### 2. Review Draft
```bash
cat email/draft_email.md
```
Rivedi il contenuto generato.

### 3. Approvazione
```bash
python approve_draft.py
```
- **Se approvi**: Il draft viene aggiunto alla memoria Redis e archiviato in `archive/`
- **Se rifiuti**: Il draft rimane per modifiche manuali

## File Draft

Il file `draft_email.md` contiene:
- **Header**: Metadata (timestamp, status, source)
- **Contenuto**: Email generata dall'agente

## Archive

Le email approvate vengono archiviate con timestamp:
- Formato: `email_YYYYMMDD_HHMMSS.md`
- Contengono header approvazione
- Sono parte della memoria incrementale

## Note

- Il draft viene **eliminato** dopo approvazione
- Solo email **approvate** vengono aggiunte alla memoria Redis
- L'archivio mantiene lo storico completo delle email inviate

