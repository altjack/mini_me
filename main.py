#!/usr/bin/env python3
"""
Main orchestrator per Daily Report Workflow.

Questo script coordina l'intero workflow:
1. Aggiornamento dati GA4
2. Esecuzione agente per generare draft email
3. Validazione e approvazione email

Usage:
    uv run main.py [--auto-approve]
    
Options:
    --auto-approve    Approva automaticamente il draft senza review manuale

Workflow:
    GA4 extraction -> Agent execution -> Email approval -> Archive
"""

import sys
import os
import yaml
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Aggiungi directory corrente al path
sys.path.append(os.path.dirname(__file__))

# Import dei workflow
from run_agent import run_agent_workflow, setup_logging, load_config, ensure_directories
from approve_draft import approve_draft_workflow, show_memory_stats

# Import service layer
from ga4_extraction.factory import GA4ResourceFactory
from ga4_extraction.services import GA4DataService


def update_ga4_data(config: dict, logger: logging.Logger) -> tuple:
    """
    Esegue l'aggiornamento dei dati GA4 e salva in database.
    
    Usa service layer per gestione centralizzata con check esistenza dati.
    
    Args:
        config: Configurazione caricata
        logger: Logger per messaggi
    
    Returns:
        Tuple (success: bool, date: str) - data estratta se successo
    """
    try:
        # Crea risorse usando factory
        db, cache = GA4ResourceFactory.create_from_config(config)
        
        # Crea service
        with GA4DataService(db, cache) as service:
            # Estrai e salva per ieri (con check esistenza automatico)
            success, target_date = service.extract_and_save_for_yesterday(force=False)
            
            if success:
                logger.info(f"✓ Dati disponibili per {target_date}")
                return True, target_date
            else:
                logger.error("Errore estrazione/salvataggio dati")
                return False, None
        
    except Exception as e:
        logger.error(f"Errore update GA4 data: {e}", exc_info=True)
        return False, None


def verify_ga4_data(output_dir: str, logger: logging.Logger) -> tuple[bool, list]:
    """
    Verifica che i file CSV GA4 siano stati generati.
    
    Args:
        output_dir: Directory contenente i CSV
        logger: Logger per messaggi
    
    Returns:
        Tuple (successo: bool, lista_file: list)
    """
    if not os.path.exists(output_dir):
        logger.error(f"Directory output non trovata: {output_dir}")
        return False, []
    
    # Cerca file CSV
    csv_files = [f for f in os.listdir(output_dir) if f.endswith('.csv')]
    
    if not csv_files:
        logger.error(f"Nessun file CSV trovato in {output_dir}")
        return False, []
    
    logger.info(f"✓ Trovati {len(csv_files)} file CSV")
    return True, csv_files


def main():
    """
    Funzione principale orchestratore workflow.
    """
    # Parse argomenti
    parser = argparse.ArgumentParser(description='Daily Report Workflow Orchestrator')
    parser.add_argument(
        '--auto-approve', 
        action='store_true',
        help='Approva automaticamente il draft senza review manuale'
    )
    args = parser.parse_args()
    
    # Header
    print("=" * 80)
    print("  🚀 DAILY REPORT WORKFLOW - Orchestratore Completo")
    print("=" * 80)
    print()
    
    try:
        # ========== SETUP ==========
        print("📋 Setup iniziale...")
        
        # Carica configurazione
        config = load_config()
        print("✓ Configurazione caricata")
        
        # Setup logging
        logger = setup_logging(config)
        logger.info("=== INIZIO WORKFLOW COMPLETO ===")
        
        # Assicura directory
        ensure_directories(config)
        print("✓ Directory verificate")
        print()
        
        # ========== STEP 1: UPDATE GA4 DATA ==========
        print("=" * 80)
        print("  [1/3] 📊 AGGIORNAMENTO DATI GA4")
        print("=" * 80)
        print()
        
        print("⏳ Estrazione dati da Google Analytics 4...")
        print("   (Questo può richiedere alcuni secondi)")
        print()
        
        success, extracted_date = update_ga4_data(config, logger)
        
        if not success:
            print("\n❌ ERRORE: Estrazione GA4 fallita")
            print()
            print("⚠️  POSSIBILI CAUSE:")
            print("   1. Credenziali Google Analytics non valide o scadute")
            print("   2. Problema di connessione alla API di Google")
            print("   3. Configurazione GA4 non corretta")
            print("   4. Database non accessibile")
            print()
            print("📝 VERIFICA:")
            print("   - File credentials/token.json è presente e valido")
            print("   - La configurazione in ga4_extraction/config.py è corretta")
            print("   - Database SQLite: data/ga4_data.db è accessibile")
            print("   - Log dettagliati in: ga4_extraction.log")
            print()
            logger.error("Workflow interrotto: estrazione GA4 fallita")
            sys.exit(1)
        
        print("✓ Estrazione completata con successo")
        print(f"✓ Dati salvati in database per {extracted_date}")
        print()
        
        # Mostra statistiche database
        db_path = config.get('database', {}).get('sqlite', {}).get('path', 'data/ga4_data.db')
        db = GA4Database(db_path)
        stats = db.get_statistics()
        
        print("📊 Statistiche Database:")
        print(f"   • Record totali: {stats['record_count']}")
        print(f"   • Periodo: {stats['min_date']} → {stats['max_date']}")
        print(f"   • Media conversioni SWI: {stats['avg_swi_conversioni']:.0f}")
        print()
        
        db.close()
        
        logger.info(f"STEP 1 completato: dati salvati per {extracted_date}")
        
        # ========== STEP 2: RUN AGENT ==========
        print("=" * 80)
        print("  [2/3] 🤖 ESECUZIONE AGENTE AI")
        print("=" * 80)
        print()
        
        print("🧠 Creazione agente con memoria Redis...")
        print("📊 Analisi dati GA4...")
        print("✍️  Generazione draft email...")
        print()
        
        try:
            draft_path = run_agent_workflow(config, logger, skip_data_check=True)
            print(f"✓ Draft generato con successo: {draft_path}")
            print()
            logger.info(f"STEP 2 completato: draft salvato in {draft_path}")
            
        except Exception as e:
            print(f"\n❌ ERRORE: Esecuzione agente fallita")
            print(f"   {str(e)}")
            print()
            
            if "Redis" in str(e):
                print("⚠️  PROBLEMA REDIS:")
                print("   1. Redis è installato? -> brew install redis")
                print("   2. Redis è avviato? -> redis-server")
                print("   3. Memoria caricata? -> uv run agent/load_memory.py")
            else:
                print("📝 VERIFICA:")
                print("   - Log dettagliati in: agent_execution.log")
                print("   - Configurazione agente in: config.yaml")
            print()
            
            logger.error(f"Workflow interrotto: esecuzione agente fallita - {e}")
            sys.exit(1)
        
        # ========== STEP 3: EMAIL VALIDATION ==========
        print("=" * 80)
        print("  [3/3] 📧 VALIDAZIONE E APPROVAZIONE EMAIL")
        print("=" * 80)
        print()
        
        if args.auto_approve:
            print("🤖 Modalità auto-approve attiva")
            print("   (Il draft sarà approvato automaticamente)")
            print()
            interactive = False
        else:
            print("👤 Modalità interattiva")
            print("   (Richiesta approvazione manuale)")
            print()
            interactive = True
        
        try:
            approved, archive_path = approve_draft_workflow(config, interactive=interactive)
            
            if approved:
                print("\n✓ Draft approvato con successo!")
                print("💾 Aggiunto alla memoria Redis")
                print(f"📁 Archiviato in: {archive_path}")
                print()
                
                # Mostra statistiche memoria
                show_memory_stats()
                
                logger.info(f"STEP 3 completato: draft approvato e archiviato in {archive_path}")
                
            else:
                print("\n❌ Draft rifiutato dall'utente")
                print()
                print("Il draft è stato mantenuto per modifiche future.")
                print()
                print("📝 OPZIONI:")
                print("   1. Modifica config.yaml e riesegui: uv run main.py")
                print(f"   2. Modifica manualmente il draft: {draft_path}")
                print("   3. Riapprova manualmente: uv run approve_draft.py")
                print()
                
                logger.info("STEP 3: draft rifiutato dall'utente")
                sys.exit(0)  # Exit normale, non errore
                
        except Exception as e:
            print(f"\n❌ ERRORE: Approvazione fallita")
            print(f"   {str(e)}")
            print()
            logger.error(f"Workflow interrotto: approvazione fallita - {e}")
            sys.exit(1)
        
        # ========== SUCCESS FINALE ==========
        print("\n")
        print("=" * 80)
        print("  ✅ WORKFLOW COMPLETATO CON SUCCESSO")
        print("=" * 80)
        print()
        print("📊 RIEPILOGO:")
        print(f"   1. ✓ Dati GA4 aggiornati (database: {extracted_date})")
        print(f"   2. ✓ Draft email generato")
        print(f"   3. ✓ Email approvata e archiviata")
        print()
        print("🎉 Il processo di daily report è stato completato!")
        print()
        print("📅 PROSSIMA ESECUZIONE:")
        print("   python main.py")
        print()
        print("💡 INFO DATABASE:")
        print("   - SQLite: data/ga4_data.db")
        print("   - Redis cache: ultimi 14 giorni")
        print()
        
        logger.info("=== WORKFLOW COMPLETATO CON SUCCESSO ===")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Workflow interrotto dall'utente")
        if 'logger' in locals():
            logger.warning("Workflow interrotto dall'utente")
        sys.exit(130)
    
    except FileNotFoundError as e:
        print(f"\n❌ ERRORE: File non trovato - {e}")
        if 'logger' in locals():
            logger.error(f"File non trovato: {e}")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ ERRORE IMPREVISTO: {e}")
        if 'logger' in locals():
            logger.error(f"Errore imprevisto: {e}", exc_info=True)
        
        print()
        print("📝 Per diagnostica dettagliata, controlla:")
        print("   - agent_execution.log")
        print("   - ga4_extraction.log")
        print()
        
        sys.exit(1)


if __name__ == "__main__":
    main()
