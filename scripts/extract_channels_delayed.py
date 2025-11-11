#!/usr/bin/env python3
"""
Script per estrazione ritardata sessioni per canale (D-2).

GA4 ha un ritardo di ~48 ore per i dati per canale.
Questo script estrae i dati per 2 giorni fa e li salva nel database.

Usage:
    # Estrai sessioni canale per D-2 (default)
    uv run extract_channels_delayed.py
    
    # Estrai per una data specifica
    uv run extract_channels_delayed.py --date 2025-11-05
    
    # Estrai per range di date
    uv run extract_channels_delayed.py --days 7

Cron Setup (esecuzione giornaliera):
    # Aggiungi a crontab per esecuzione automatica alle 9:00
    0 9 * * * cd /path/to/daily_report && uv run extract_channels_delayed.py
"""

import sys
import os
import logging
import argparse
from datetime import datetime, timedelta

# Aggiungi directory parent al path (per import da ga4_extraction)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ga4_extraction.database import GA4Database
from ga4_extraction.extraction import extract_sessions_channels_delayed

# Configurazione logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'extract_channels_delayed.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """
    Funzione principale per estrazione ritardata canali.
    """
    parser = argparse.ArgumentParser(
        description='Estrae sessioni per canale con ritardo di 48h (D-2)'
    )
    
    parser.add_argument(
        '--date',
        help='Data specifica da estrarre (YYYY-MM-DD). Default: D-2 (2 giorni fa)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=1,
        help='Numero di giorni da estrarre a ritroso da D-2 (default: 1)'
    )
    parser.add_argument(
        '--db-path',
        default='data/ga4_data.db',
        help='Path database SQLite (default: data/ga4_data.db)'
    )
    
    args = parser.parse_args()
    
    # Header
    print("=" * 80)
    print("  📊 ESTRAZIONE RITARDATA SESSIONI PER CANALE (D-2)")
    print("=" * 80)
    print()
    
    try:
        # Setup database
        logger.info(f"Connessione database: {args.db_path}")
        db = GA4Database(args.db_path)
        
        # Determina date da estrarre
        if args.date:
            # Data specifica - valida prima di procedere
            target_dates = [args.date]
            logger.info(f"Modalità data specifica: {args.date}")
            
            # Validazione data manuale
            from ga4_extraction.extraction import validate_date_for_channels
            is_valid, message = validate_date_for_channels(args.date)
            if not is_valid:
                print(f"\n⚠️  WARNING: {message}")
                print(f"⚠️  La data specificata è troppo recente per avere dati canale GA4")
                print(f"💡 SUGGERIMENTO: Usa una data >= D-2 (oggi - 2 giorni)\n")
                
                response = input("Procedere comunque con l'estrazione? [y/N]: ")
                if response.lower() != 'y':
                    print("Operazione annullata")
                    db.close()
                    return 0
        else:
            # D-2 (2 giorni fa) + eventuali giorni aggiuntivi
            target_dates = []
            for i in range(args.days):
                date = datetime.now() - timedelta(days=2 + i)
                target_dates.append(date.strftime('%Y-%m-%d'))
            
            logger.info(f"Modalità automatica: D-2 = {target_dates[0]}")
        
        print(f"📅 Date da estrarre: {', '.join(target_dates)}")
        print(f"⏱️  Ritardo GA4: ~48 ore")
        print()
        
        # Verifica che le date abbiano già metriche principali
        cursor = db.conn.cursor()
        for date in target_dates:
            cursor.execute("SELECT date FROM daily_metrics WHERE date = ?", (date,))
            if not cursor.fetchone():
                print(f"⚠️  ATTENZIONE: {date} non ha metriche principali nel database")
                print(f"   Esegui prima: uv run backfill_missing_dates.py --date {date}")
                print()
        
        print("=" * 80)
        print("  🚀 INIZIO ESTRAZIONE")
        print("=" * 80)
        print()
        
        success_count = 0
        failed_count = 0
        
        for i, date in enumerate(target_dates, 1):
            print(f"[{i}/{len(target_dates)}] Estrazione canali per {date}...")
            
            success = extract_sessions_channels_delayed(date, db)
            
            if success:
                success_count += 1
                print(f"✓ OK - Dati salvati")
            else:
                failed_count += 1
                print(f"✗ FALLITO - Dati non disponibili o errore")
            
            print()
        
        # Riepilogo
        print("=" * 80)
        print("  ✅ ESTRAZIONE COMPLETATA")
        print("=" * 80)
        print()
        print(f"📊 Risultati:")
        print(f"   • Successo: {success_count}")
        print(f"   • Falliti: {failed_count}")
        print(f"   • Totale: {success_count + failed_count}")
        print()
        
        if failed_count > 0:
            print("⚠️  NOTA: Alcuni fallimenti potrebbero essere dovuti a:")
            print("   1. Dati GA4 non ancora disponibili (ritardo > 48h)")
            print("   2. Nessuna sessione per canale in quella data")
            print("   3. Errore di connessione API GA4")
            print()
            print("💡 SUGGERIMENTO: Riprova tra qualche ora o controlla i log")
            print()
        
        # Mostra statistiche database
        stats = db.get_statistics()
        print(f"📈 Statistiche Database:")
        print(f"   • Record totali: {stats['record_count']}")
        print(f"   • Periodo: {stats['min_date']} → {stats['max_date']}")
        print()
        
        # Chiudi connessione
        db.close()
        
        logger.info(f"Estrazione completata: {success_count} successi, {failed_count} falliti")
        
        return 0 if failed_count == 0 else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Operazione interrotta dall'utente")
        if 'db' in locals():
            db.close()
        return 130
    
    except Exception as e:
        logger.error(f"Errore durante estrazione: {e}", exc_info=True)
        print(f"\n❌ ERRORE: {e}")
        print()
        print("📝 Controlla il log per dettagli: extract_channels_delayed.log")
        
        if 'db' in locals():
            db.close()
        
        return 1


if __name__ == '__main__':
    sys.exit(main())

