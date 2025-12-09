# Guida Completa agli Agenti Claude Code

## Panoramica

Questa documentazione fornisce una guida completa per tutti gli 83 agenti specializzati disponibili nella cartella `@agents/`, con ruoli specifici, criteri di utilizzo e pattern di concatenazione per task complessi che richiedono l'uso di più agenti.

## 📑 Indice

- [Panoramica](#panoramica)
- [Principi di Utilizzo](#principi-di-utilizzo)
- [Quick Reference - Agenti Più Utilizzati](#-quick-reference---agenti-più-utilizzati)
- [Categorizzazione degli Agenti](#categorizzazione-degli-agenti)
  - [🏗️ Architettura e Design di Sistema](#️-architettura-e-design-di-sistema)
  - [💻 Linguaggi di Programmazione](#-linguaggi-di-programmazione)
  - [🚀 Infrastruttura e Operazioni](#-infrastruttura-e-operazioni)
  - [🔒 Qualità e Sicurezza](#-qualità-e-sicurezza)
  - [📊 Dati e AI](#-dati-e-ai)
  - [📚 Documentazione e Technical Writing](#-documentazione-e-technical-writing)
  - [💼 Business e Operazioni](#-business-e-operazioni)
  - [🔗 Domini Specializzati](#-domini-specializzati)
  - [🔍 SEO e Ottimizzazione Contenuti](#-seo-e-ottimizzazione-contenuti)
- [Pattern di Concatenazione Multi-Agente](#pattern-di-concatenazione-multi-agente)
- [Guida Selezione Agenti](#guida-selezione-agenti)
- [Best Practices](#best-practices)
- [Esempi di Utilizzo](#esempi-di-utilizzo)

## Principi di Utilizzo

### Regole Comportamentali
- **Comportamento proattivo**: Gli agenti devono essere utilizzati proattivamente quando il task richiede le loro competenze specifiche
- **Analisi approfondita**: Prima di ogni chiamata di funzione, pianifica estensivamente e rifletti sui risultati delle chiamate precedenti
- **Risoluzione completa**: Continua fino a quando la richiesta dell'utente non è completamente risolta
- **Adattamento al progetto**: Quando si lavora su un progetto esistente, adattati alle convenzioni esistenti

### Regole di Codifica
- **Principi SOLID**: Segui i principi SOLID, DRY, KISS, YAGNI
- **Codice robusto**: Ogni implementazione deve essere robusta e ben pensata
- **Focus specifico**: Limita le modifiche a ciò che è stato richiesto, senza refactoring non richiesto
- **PyQt5 preferito**: Per GUI development, preferisci PyQt5 invece di tkinter
- **main.py semplice**: Mantieni main.py semplice senza configurazioni kwargs eccessive

## 🚀 Quick Reference - Agenti Più Utilizzati

### Per Scenario Comune

| Scenario | Agente Consigliato | Note |
|----------|-------------------|------|
| **API REST/GraphQL** | `backend-architect`, `fastapi-pro`, `django-pro` | FastAPI per performance, Django per full-stack |
| **Frontend Moderno** | `frontend-developer`, `ui-ux-designer` | React 19, Next.js 15, design systems |
| **Problemi Produzione** | `incident-responder`, `devops-troubleshooter` | Response immediata e troubleshooting |
| **Security Audit** | `security-auditor`, `code-reviewer` | Vulnerabilità, OWASP, best practices |
| **AI/ML Projects** | `ai-engineer`, `ml-engineer`, `mlops-engineer` | LLM, RAG, model deployment |
| **Database Issues** | `database-optimizer`, `database-admin` | Performance, backup, migrations |
| **Mobile Apps** | `ios-developer`, `flutter-expert`, `mobile-developer` | Native iOS o cross-platform |
| **Performance** | `performance-engineer`, `database-optimizer` | Profiling, bottleneck analysis |
| **Testing** | `test-automator`, `tdd-orchestrator` | Unit, integration, e2e tests |
| **Documentation** | `docs-architect`, `api-documenter` | Technical docs, API specs |

### Comparazione Framework Web Python

| Caratteristica | `fastapi-pro` | `django-pro` |
|----------------|---------------|--------------|
| **Performance** | ⚡ Eccellente (async-first) | ✅ Ottima (supporto async) |
| **Use Case** | API, microservizi, real-time | Full-stack, admin, CMS |
| **Curva Apprendimento** | 📊 Media | 📈 Alta |
| **Ecosystem** | 🆕 Moderno, leggero | 🏢 Maturo, batteries included |
| **Auto-Documentation** | ✅ OpenAPI automatica | ➕ Con DRF |
| **Admin Panel** | ❌ Non incluso | ✅ Built-in potente |
| **ORM** | SQLAlchemy 2.0 (async) | Django ORM (async) |
| **Best For** | Nuovi progetti API, microservizi | Enterprise apps, admin panels |

### Selezione Rapida per Linguaggio

| Se usi... | Scegli... |
|-----------|-----------|
| Python | `python-pro`, `fastapi-pro`, `django-pro` |
| JavaScript/TypeScript | `javascript-pro`, `typescript-pro`, `frontend-developer` |
| Java | `java-pro` |
| C/C++ | `c-pro`, `cpp-pro` |
| Rust | `rust-pro` |
| Go | `golang-pro` |
| Mobile (iOS) | `ios-developer` |
| Mobile (Cross-platform) | `flutter-expert`, `mobile-developer` |

## Categorizzazione degli Agenti

### 🏗️ Architettura e Design di Sistema

#### Architettura Core
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `backend-architect` | opus | Progettazione API RESTful, microservizi, schemi database | Creazione nuovi servizi backend, design API, architettura microservizi |
| `frontend-developer` | sonnet | Componenti React, layout responsive, gestione stato client-side | Sviluppo UI/UX, componenti React, ottimizzazione frontend |
| `graphql-architect` | opus | Schemi GraphQL, resolver, architettura federata | API GraphQL, federazione, query complesse |
| `architect-review` | opus | Analisi consistenza architetturale, validazione pattern | Review architetturale, validazione design patterns |
| `cloud-architect` | opus | Design infrastruttura AWS/Azure/GCP, ottimizzazione costi | Architettura cloud, scalabilità, ottimizzazione costi |
| `hybrid-cloud-architect` | opus | Strategie multi-cloud, ambienti ibridi | Architetture ibride, migrazione cloud, strategie multi-cloud |
| `kubernetes-architect` | opus | Infrastruttura cloud-native, GitOps | Container orchestration, cloud-native, CI/CD |

#### UI/UX e Mobile
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `ui-ux-designer` | sonnet | Design interfacce, wireframe, design system | Design UI/UX, wireframing, design system |
| `ui-visual-validator` | sonnet | Test regressione visiva, verifica UI | Testing UI, validazione visiva, QA frontend |
| `mobile-developer` | sonnet | Sviluppo app React Native e Flutter | App mobile cross-platform, React Native, Flutter |
| `ios-developer` | sonnet | Sviluppo nativo iOS con Swift/SwiftUI | App iOS native, Swift, SwiftUI |
| `flutter-expert` | sonnet | Sviluppo Flutter avanzato con gestione stato | App Flutter complesse, gestione stato avanzata |

### 💻 Linguaggi di Programmazione

#### Sistemi e Low-Level
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `c-pro` | sonnet | Programmazione di sistema, gestione memoria, interfacce OS | Sistemi embedded, programmazione di sistema, ottimizzazione performance |
| `cpp-pro` | sonnet | C++ moderno con RAII, smart pointers, STL | Sistemi ad alte prestazioni, giochi, applicazioni desktop |
| `rust-pro` | sonnet | Programmazione sicura, pattern ownership | Sistemi sicuri, performance critiche, blockchain |
| `golang-pro` | sonnet | Programmazione concorrente, goroutines, channels | Microservizi, sistemi distribuiti, API ad alte prestazioni |

#### Web e Applicazioni
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `javascript-pro` | sonnet | JavaScript moderno, ES6+, pattern async, Node.js | Sviluppo web full-stack, Node.js, applicazioni JavaScript |
| `typescript-pro` | sonnet | TypeScript avanzato, sistemi di tipo, generics | Applicazioni enterprise, type safety, progetti complessi |
| `python-pro` | sonnet | Python 3.12+, async, ottimizzazione performance | Data science, backend API, automazione, scripting |
| `fastapi-pro` | sonnet | FastAPI con async, SQLAlchemy 2.0, Pydantic V2, WebSockets | API ad alte prestazioni, microservizi async, real-time apps |
| `django-pro` | sonnet | Django 5.x, async views, DRF, Celery, Django Channels | Web app Django scalabili, API REST/GraphQL, sistemi enterprise |
| `ruby-pro` | sonnet | Ruby con metaprogrammazione, pattern Rails | Applicazioni web Ruby on Rails, gem development |
| `php-pro` | sonnet | PHP moderno, framework, ottimizzazione performance | Siti web, CMS, applicazioni PHP enterprise |

#### Enterprise e JVM
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `java-pro` | sonnet | Java moderno, streams, concorrenza, ottimizzazione JVM | Applicazioni enterprise, sistemi distribuiti, Android |
| `scala-pro` | sonnet | Scala enterprise, programmazione funzionale | Big data, sistemi distribuiti, applicazioni Scala |
| `csharp-pro` | sonnet | C# con framework .NET e pattern | Applicazioni Windows, .NET, Unity development |

#### Piattaforme Specializzate
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `elixir-pro` | sonnet | Elixir con pattern OTP e framework Phoenix | Sistemi real-time, applicazioni distribuite, Phoenix |
| `unity-developer` | sonnet | Sviluppo giochi Unity e ottimizzazione | Giochi, simulazioni, applicazioni 3D |
| `minecraft-bukkit-pro` | sonnet | Sviluppo plugin server Minecraft | Plugin Minecraft, modding, server management |
| `sql-pro` | sonnet | Query SQL complesse e ottimizzazione database | Query database complesse, ottimizzazione performance |

### 🚀 Infrastruttura e Operazioni

#### DevOps e Deployment
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `devops-troubleshooter` | sonnet | Debug produzione, analisi log, troubleshooting deployment | Incidenti produzione, debug sistemi, troubleshooting |
| `deployment-engineer` | sonnet | Pipeline CI/CD, containerizzazione, deployment cloud | Automazione deployment, CI/CD, containerizzazione |
| `terraform-specialist` | opus | Infrastructure as Code con moduli Terraform | Infrastruttura cloud, automazione, IaC |
| `dx-optimizer` | sonnet | Ottimizzazione developer experience e tooling | Miglioramento workflow sviluppo, tooling, automazione |

#### Gestione Database
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `database-optimizer` | opus | Ottimizzazione query, design indici, strategie migrazione | Performance database, ottimizzazione query, scaling |
| `database-admin` | sonnet | Operazioni database, backup, replica, monitoring | Gestione database, backup, disaster recovery |

#### Incident Response e Network
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `incident-responder` | opus | Gestione incidenti produzione e risoluzione | Incidenti critici, outage, response immediata |
| `network-engineer` | sonnet | Debug network, load balancing, analisi traffico | Problemi di rete, load balancing, connettività |

### 🔒 Qualità e Sicurezza

#### Qualità Codice e Review
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `code-reviewer` | opus | Code review con focus sicurezza e affidabilità produzione | Review codice, best practices, qualità |
| `security-auditor` | opus | Valutazione vulnerabilità e compliance OWASP | Audit sicurezza, compliance, vulnerabilità |
| `backend-security-coder` | opus | Pratiche coding sicure backend, implementazione sicurezza API | Sviluppo sicuro backend, API security |
| `frontend-security-coder` | opus | Prevenzione XSS, implementazione CSP, sicurezza client-side | Sicurezza frontend, prevenzione attacchi web |
| `mobile-security-coder` | opus | Pattern sicurezza mobile, WebView security, autenticazione biometrica | Sicurezza mobile, app security, autenticazione |

#### Testing e Debugging
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `test-automator` | sonnet | Creazione suite test complete (unit, integration, e2e) | Automazione test, TDD, quality assurance |
| `tdd-orchestrator` | sonnet | Guida metodologia Test-Driven Development | Implementazione TDD, strategie testing |
| `debugger` | sonnet | Risoluzione errori e analisi fallimenti test | Debug, risoluzione bug, troubleshooting |
| `error-detective` | sonnet | Analisi log e riconoscimento pattern errori | Analisi errori, pattern recognition, root cause |

#### Performance e Observability
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `performance-engineer` | opus | Profiling applicazioni e ottimizzazione | Ottimizzazione performance, profiling, scaling |
| `observability-engineer` | opus | Monitoring produzione, distributed tracing, gestione SLI/SLO | Monitoring, observability, SRE |
| `search-specialist` | haiku | Ricerca web avanzata e sintesi informazioni | Ricerca informazioni, analisi web |

### 📊 Dati e AI

#### Data Engineering e Analytics
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `data-scientist` | opus | Analisi dati, query SQL, operazioni BigQuery | Analisi dati, machine learning, business intelligence |
| `data-engineer` | sonnet | Pipeline ETL, data warehouse, architetture streaming | Data pipeline, ETL, data infrastructure |

#### Machine Learning e AI
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `ai-engineer` | opus | Applicazioni LLM, sistemi RAG, pipeline prompt | AI applications, LLM, RAG systems |
| `ml-engineer` | opus | Pipeline ML, model serving, feature engineering | Machine learning, model deployment, ML ops |
| `mlops-engineer` | opus | Infrastruttura ML, experiment tracking, model registry | ML infrastructure, MLOps, experiment management |
| `prompt-engineer` | opus | Ottimizzazione prompt LLM e engineering | Prompt optimization, LLM tuning, AI prompts |

### 📚 Documentazione e Technical Writing

| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `docs-architect` | opus | Generazione documentazione tecnica completa | Documentazione tecnica, architettura docs |
| `api-documenter` | sonnet | Specifiche OpenAPI/Swagger e documentazione sviluppatori | API documentation, OpenAPI, developer docs |
| `reference-builder` | haiku | Riferimenti tecnici e documentazione API | Reference docs, API references |
| `tutorial-engineer` | sonnet | Tutorial step-by-step e contenuti educativi | Tutorial, guide, educational content |
| `mermaid-expert` | sonnet | Creazione diagrammi (flowchart, sequenze, ERD) | Diagrammi, visualizzazione, documentazione |

### 💼 Business e Operazioni

#### Business Analysis e Finanza
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `business-analyst` | sonnet | Analisi metriche, reporting, tracking KPI | Business analysis, KPI, reporting |
| `quant-analyst` | opus | Modellazione finanziaria, strategie trading, analisi mercato | Finanza quantitativa, trading, risk management |
| `risk-manager` | sonnet | Monitoraggio e gestione rischio portfolio | Risk management, compliance, risk assessment |

#### Marketing e Vendite
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `content-marketer` | sonnet | Blog post, social media, campagne email | Content marketing, social media, email marketing |
| `sales-automator` | haiku | Email fredde, follow-up, generazione proposte | Sales automation, lead generation, prospecting |

#### Support e Legale
| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `customer-support` | sonnet | Ticket supporto, risposte FAQ, comunicazione clienti | Customer service, support tickets, FAQ |
| `hr-pro` | opus | Operazioni HR, policy, relazioni dipendenti | HR operations, policies, employee relations |
| `legal-advisor` | opus | Privacy policy, terms of service, documentazione legale | Legal compliance, privacy, terms of service |

### 🔗 Domini Specializzati

| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `blockchain-developer` | sonnet | App Web3, smart contract, protocolli DeFi | Blockchain, Web3, smart contracts, DeFi |
| `payment-integration` | sonnet | Integrazione processori pagamento (Stripe, PayPal) | Payment processing, e-commerce, fintech |
| `legacy-modernizer` | sonnet | Refactoring codice legacy e modernizzazione | Legacy code, modernization, refactoring |
| `context-manager` | haiku | Gestione contesto multi-agente | Multi-agent coordination, context management |

### 🔍 SEO e Ottimizzazione Contenuti

| Agente | Modello | Ruolo Specifico | Quando Utilizzare |
|--------|---------|-----------------|-------------------|
| `seo-content-auditor` | sonnet | Analisi qualità contenuti, valutazione segnali E-E-A-T | SEO content audit, content quality |
| `seo-meta-optimizer` | haiku | Ottimizzazione meta title e description | Meta tags optimization, SEO basics |
| `seo-keyword-strategist` | haiku | Analisi keyword e variazioni semantiche | Keyword research, SEO strategy |
| `seo-structure-architect` | haiku | Struttura contenuti e schema markup | Content structure, schema markup |
| `seo-snippet-hunter` | haiku | Formattazione featured snippet | Featured snippets, SERP optimization |
| `seo-content-refresher` | haiku | Analisi freschezza contenuti | Content freshness, content updates |
| `seo-cannibalization-detector` | haiku | Rilevamento sovrapposizione keyword | Keyword cannibalization, content overlap |
| `seo-authority-builder` | sonnet | Analisi segnali E-E-A-T | E-A-T signals, authority building |
| `seo-content-writer` | sonnet | Creazione contenuti ottimizzati SEO | SEO content writing, content creation |
| `seo-content-planner` | haiku | Pianificazione contenuti e topic cluster | Content planning, topic clusters |

## Pattern di Concatenazione Multi-Agente

### 🔄 Workflow Sequenziali

#### Sviluppo Feature Completa
```
"Implementa autenticazione utente"
→ backend-architect (design API) 
→ frontend-developer (UI components)
→ test-automator (test suite)
→ security-auditor (security review)
→ performance-engineer (ottimizzazione)
```

#### Ottimizzazione Performance
```
"Ottimizza processo checkout"
→ performance-engineer (analisi bottleneck)
→ database-optimizer (ottimizzazione query)
→ frontend-developer (ottimizzazione UI)
→ observability-engineer (monitoring)
```

#### Incident Response
```
"Debug alto utilizzo memoria"
→ incident-responder (response immediata)
→ devops-troubleshooter (analisi log)
→ error-detective (pattern recognition)
→ performance-engineer (soluzioni)
```

#### Setup Infrastruttura
```
"Configura disaster recovery"
→ database-admin (backup strategy)
→ database-optimizer (performance)
→ terraform-specialist (infrastructure as code)
→ observability-engineer (monitoring)
```

### ⚡ Esecuzione Parallela

#### Analisi Multi-Dimensionale
```
performance-engineer + database-optimizer → Analisi combinata
security-auditor + code-reviewer → Review completa
ui-ux-designer + frontend-developer → Design + implementazione
```

### 🔀 Routing Condizionale

#### Debug Intelligente
```
debugger → [backend-architect | frontend-developer | devops-troubleshooter]
basato su: tipo di errore, stack trace, contesto
```

### ✅ Pipeline di Validazione

#### Implementazione Sicura
```
payment-integration → security-auditor → Implementazione validata
api-documenter → code-reviewer → Documentazione verificata
```

## Guida Selezione Agenti

### 🎯 Per Tipo di Task

#### Architettura e Pianificazione
- **Design API**: `backend-architect`
- **Infrastruttura Cloud**: `cloud-architect`
- **Design UI/UX**: `ui-ux-designer`
- **Review Architetturale**: `architect-review`

#### Sviluppo per Linguaggio
- **Sistemi**: `c-pro`, `cpp-pro`, `rust-pro`, `golang-pro`
- **Web**: `javascript-pro`, `typescript-pro`, `python-pro`, `fastapi-pro`, `django-pro`, `ruby-pro`, `php-pro`
- **Enterprise**: `java-pro`, `csharp-pro`, `scala-pro`
- **Mobile**: `ios-developer`, `flutter-expert`, `mobile-developer`

#### Operazioni e Infrastruttura
- **Problemi Produzione**: `devops-troubleshooter`
- **Incidenti Critici**: `incident-responder`
- **Performance Database**: `database-optimizer`
- **Infrastructure as Code**: `terraform-specialist`

#### Qualità e Sicurezza
- **Code Review**: `code-reviewer`
- **Security Audit**: `security-auditor`
- **Creazione Test**: `test-automator`
- **Problemi Performance**: `performance-engineer`

#### Dati e Machine Learning
- **Analisi Dati**: `data-scientist`
- **Applicazioni LLM**: `ai-engineer`
- **Sviluppo ML**: `ml-engineer`
- **ML Operations**: `mlops-engineer`

### 🎯 Per Complessità

#### Task Semplici (Haiku)
- `context-manager`, `reference-builder`, `sales-automator`
- Agenti SEO di base: `seo-meta-optimizer`, `seo-keyword-strategist`

#### Task Standard (Sonnet)
- Tutti i linguaggi di programmazione
- Sviluppo frontend/backend
- Testing e debugging
- Operazioni DevOps

#### Task Complessi (Opus)
- Architettura e design
- Security e compliance
- AI/ML avanzato
- Business critical

## Best Practices

### 🎯 Delegazione Task
1. **Selezione automatica** - Lascia che Claude Code analizzi il contesto
2. **Requisiti chiari** - Specifica vincoli, tech stack, standard qualità
3. **Fiducia nella specializzazione** - Ogni agente è ottimizzato per il suo dominio

### 🔗 Workflow Multi-Agente
1. **Richieste ad alto livello** - Permetti agli agenti di coordinare task complessi
2. **Preservazione contesto** - Assicura che gli agenti abbiano informazioni necessarie
3. **Review integrazione** - Verifica come gli output degli agenti lavorano insieme

### 🎛️ Controllo Esplicito
1. **Invocazione diretta** - Specifica agenti quando serve expertise particolare
2. **Combinazione strategica** - Usa specialisti multipli per validazione
3. **Pattern di review** - Richiedi workflow di review specifici

### ⚡ Ottimizzazione Performance
1. **Monitora efficacia** - Traccia quali agenti funzionano meglio
2. **Raffinamento iterativo** - Usa feedback agenti per migliorare requisiti
3. **Matching complessità** - Allinea complessità task con capacità agenti

## Esempi di Utilizzo

### 🚀 Sviluppo Full-Stack
```
"Costruisci dashboard admin con autenticazione"
→ backend-architect (API design)
→ fastapi-pro o django-pro (implementazione backend)
→ frontend-developer (React components)
→ ui-ux-designer (design system)
→ test-automator (test coverage)
→ security-auditor (security review)
```

### ⚡ API ad Alte Prestazioni
```
"Crea API microservizi con WebSocket real-time"
→ backend-architect (architettura microservizi)
→ fastapi-pro (implementazione async, WebSocket, caching)
→ test-automator (test suite completa)
→ performance-engineer (ottimizzazione performance)
→ observability-engineer (monitoring e tracing)
```

### 🔧 Debug Produzione
```
"Sistema lento, errori 500 frequenti"
→ incident-responder (stabilizzazione)
→ devops-troubleshooter (analisi log)
→ performance-engineer (bottleneck analysis)
→ database-optimizer (query optimization)
```

### 📊 Data Science Pipeline
```
"Analizza comportamento clienti e predici churn"
→ data-scientist (analisi esplorativa)
→ ml-engineer (modello predittivo)
→ mlops-engineer (deployment pipeline)
→ observability-engineer (monitoring)
```

### 🏗️ Architettura Microservizi
```
"Progetta architettura microservizi per e-commerce"
→ backend-architect (service design)
→ cloud-architect (infrastructure)
→ security-auditor (security patterns)
→ observability-engineer (monitoring strategy)
→ terraform-specialist (infrastructure as code)
```

## 📊 Riepilogo Distribuzione Agenti

### Totale: 83 Agenti Specializzati

| Modello | Conteggio | Percentuale | Uso Principale |
|---------|-----------|-------------|----------------|
| **Opus** | 22 | 26.5% | Architettura, security, AI/ML, business critical |
| **Sonnet** | 48 | 57.8% | Sviluppo, testing, operazioni, implementazione |
| **Haiku** | 11 | 13.3% | Task rapidi, SEO, ricerca, automazione semplice |

### Categorie Principali

| Categoria | Numero Agenti | Agenti Chiave |
|-----------|---------------|---------------|
| **Linguaggi di Programmazione** | 20 | `python-pro`, `javascript-pro`, `typescript-pro`, `fastapi-pro`, `django-pro` |
| **Architettura & Design** | 7 | `backend-architect`, `cloud-architect`, `architect-review` |
| **Security & Quality** | 9 | `security-auditor`, `code-reviewer`, `test-automator` |
| **Infrastructure & DevOps** | 8 | `devops-troubleshooter`, `terraform-specialist`, `kubernetes-architect` |
| **AI & Data** | 9 | `ai-engineer`, `ml-engineer`, `data-scientist` |
| **Mobile & Frontend** | 6 | `frontend-developer`, `ios-developer`, `flutter-expert` |
| **SEO & Content** | 10 | `seo-content-auditor`, `seo-content-writer` |
| **Business & Operations** | 8 | `business-analyst`, `legal-advisor`, `hr-pro` |
| **Documentation** | 5 | `docs-architect`, `api-documenter`, `mermaid-expert` |

### Novità e Aggiornamenti (2024/2025)

#### Agenti Framework Python Moderni
- **`fastapi-pro`** (sonnet): Expert FastAPI con async, SQLAlchemy 2.0, Pydantic V2, WebSockets
- **`django-pro`** (sonnet): Expert Django 5.x con async views, DRF, Celery, Django Channels

#### Best Practices per la Selezione
1. **API ad alte prestazioni**: Usa `fastapi-pro` per microservizi async e real-time
2. **Applicazioni enterprise Django**: Usa `django-pro` per full-stack con admin panel
3. **Review architetturale**: Usa `architect-review` (non architect-reviewer)
4. **AI/LLM applications**: Chain `ai-engineer` → `mlops-engineer` → `observability-engineer`

## Conclusione

Questa guida fornisce una roadmap completa e aggiornata per l'utilizzo efficace di tutti gli **83 agenti specializzati**. Ogni agente ha un ruolo specifico e ben definito, e la loro concatenazione intelligente permette di gestire task complessi che richiedono competenze multiple.

### 🎯 Chiavi per un Utilizzo Efficace

1. **Comprendere** le competenze specifiche di ogni agente e quando utilizzarli
2. **Pianificare** workflow multi-agente per task complessi con dipendenze
3. **Fidarsi** della specializzazione di ogni agente e del loro expertise
4. **Iterare** e migliorare i pattern di utilizzo basandosi sui risultati
5. **Sfruttare** la Quick Reference per decisioni rapide
6. **Combinare** agenti complementari (es. `fastapi-pro` + `security-auditor`)

### 💡 Raccomandazioni Finali

- **Per progetti nuovi**: Parti con `backend-architect` o `frontend-developer` per definire l'architettura
- **Per ottimizzazione**: Usa `performance-engineer` + `database-optimizer` in parallelo
- **Per sicurezza**: Integra sempre `security-auditor` nei workflow critici
- **Per AI**: Chain `ai-engineer` → `mlops-engineer` per production-ready ML systems

Con questa guida, puoi sfruttare al massimo il potenziale degli agenti Claude Code per qualsiasi tipo di progetto software, dal prototipo alla produzione enterprise.
