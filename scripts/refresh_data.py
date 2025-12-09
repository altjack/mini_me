#!/usr/bin/env python3
"""
Script per aggiornare (refresh) dati GA4 già esistenti nel database.

Questo script risolve il problema delle variazioni minime nei dati GA4 che si verificano
nelle 24-48 ore successive all'estrazione iniziale. Sovrascrive i dati esistenti in DB
e Redis cache per un periodo definito (default: ultime 2 settimane).

Differenze con backfill_missing_dates.py:
- backfill: recupera SOLO date mancanti
- refresh: aggiorna TUTTE le date nel range (anche se già presenti)

Usage:
    # Refresh ultimi 14 giorni (default)
    uv run scripts/refresh_data.py
    
    # Refresh ultimi 7 giorni
    uv run scripts/refresh_data.py --days 7
    
    # Refresh range specifico
    uv run scripts/refresh_data.py --start-date 2025-11-01 --end-date 2025-11-10
    
    # Skip conferma interattiva (per automazione)
    uv run scripts/refresh_data.py --days 7 --skip-confirmation
"""

import sys
import os
import logging
import argparse
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any

# Aggiungi directory parent al path (per import da ga4_extraction)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ga4_extraction.database import GA4Database
from ga4_extraction.redis_cache import GA4RedisCache
from ga4_extraction.extraction import (
    extract_for_date,
    save_to_database,
    extract_sessions_channels_delayed
)

# Configurazione logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'refresh_data.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_date_range(args) -> Tuple[str, str]:
    """
    Calcola start_date e end_date basandosi su args CLI.
    
    Priorità:
    1. Se --start-date e --end-date: usa quelli
    2. Se --days: calcola da oggi - N giorni a ieri
    3. Default: ultime 2 settimane (14 giorni)
    
    Args:
        args: Namespace da argparse con start_date, end_date, days
    
    Returns:
        Tuple (start_date, end_date) in formato YYYY-MM-DD
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Caso 1: start_date e end_date espliciti
    if args.start_date and args.end_date:
        logger.info(f"Uso date esplicite: {args.start_date} → {args.end_date}")
        return args.start_date, args.end_date
    
    # Caso 2: solo start_date (end_date = ieri)
    if args.start_date and not args.end_date:
        end_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')
        logger.info(f"Uso start_date esplicito + end_date=ieri: {args.start_date} → {end_date}")
        return args.start_date, end_date
    
    # Caso 3: solo end_date (start_date = end_date - days)
    if args.end_date and not args.start_date:
        days = args.days if args.days else 14
        end_date_obj = datetime.strptime(args.end_date, '%Y-%m-%d')
        start_date = (end_date_obj - timedelta(days=days - 1)).strftime('%Y-%m-%d')
        logger.info(f"Uso end_date esplicito + {days} giorni: {start_date} → {args.end_date}")
        return start_date, args.end_date
    
    # Caso 4: --days specificato
    if args.days:
        days = args.days
        end_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')
        start_date = (today - timedelta(days=days)).strftime('%Y-%m-%d')
        logger.info(f"Uso --days={days}: {start_date} → {end_date}")
        return start_date, end_date
    
    # Caso 5: Default (ultime 2 settimane)
    end_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    start_date = (today - timedelta(days=14)).strftime('%Y-%m-%d')
    logger.info(f"Uso default (14 giorni): {start_date} → {end_date}")
    return start_date, end_date


def validate_and_split_dates(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Valida date range e separa date per dati principali vs canali.
    
    Logica:
    - Dati principali: tutte le date fino a D-1
    - Sessioni canali: solo date <= D-2 (ritardo GA4)
    
    Args:
        start_date: Data inizio (YYYY-MM-DD)
        end_date: Data fine (YYYY-MM-DD)
    
    Returns:
        Dict con:
        - 'all_dates': lista tutte le date nel range
        - 'dates_with_channels': date <= D-2 (canali disponibili)
        - 'dates_without_channels': date > D-2 (canali non ancora disponibili)
        - 'start_date': start_date validato
        - 'end_date': end_date validato
    """
    # Valida formato date
    try:
        start_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_obj = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError as e:
        raise ValueError(f"Formato data non valido: {e}")
    
    # Valida che start <= end
    if start_obj > end_obj:
        raise ValueError(f"start_date ({start_date}) deve essere <= end_date ({end_date})")
    
    # Genera tutte le date nel range
    all_dates = []
    current = start_obj
    while current <= end_obj:
        all_dates.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    
    # Calcola soglia D-2 per canali
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    channel_threshold = (today - timedelta(days=2)).strftime('%Y-%m-%d')
    
    # Separa date con/senza canali disponibili
    dates_with_channels = [d for d in all_dates if d <= channel_threshold]
    dates_without_channels = [d for d in all_dates if d > channel_threshold]
    
    logger.info(f"Range validato: {len(all_dates)} date totali")
    logger.info(f"  • Date con canali disponibili (<=D-2): {len(dates_with_channels)}")
    logger.info(f"  • Date senza canali (>D-2): {len(dates_without_channels)}")
    
    return {
        'all_dates': all_dates,
        'dates_with_channels': dates_with_channels,
        'dates_without_channels': dates_without_channels,
        'start_date': start_date,
        'end_date': end_date,
        'channel_threshold': channel_threshold
    }


def get_existing_dates(db: GA4Database, dates: List[str]) -> Dict[str, List[str]]:
    """
    Controlla quali date hanno già dati nel database.
    
    Args:
        db: Istanza GA4Database
        dates: Lista di date da verificare (YYYY-MM-DD)
    
    Returns:
        Dict con:
        - 'with_data': date che hanno già dati
        - 'without_data': date che non hanno dati
        - 'with_channels': date che hanno dati canali
        - 'without_channels': date che non hanno dati canali
    """
    with_data = []
    without_data = []
    with_channels = []
    without_channels = []
    
    for date in dates:
        # Check metriche principali
        if db.data_exists(date):
            with_data.append(date)
        else:
            without_data.append(date)
        
        # Check sessioni canali
        channels = db.get_sessions_by_channel(date)
        if channels and len(channels) > 0:
            with_channels.append(date)
        else:
            without_channels.append(date)
    
    logger.info(f"Verifica esistenza dati:")
    logger.info(f"  • Date con metriche: {len(with_data)}/{len(dates)}")
    logger.info(f"  • Date con canali: {len(with_channels)}/{len(dates)}")
    
    return {
        'with_data': with_data,
        'without_data': without_data,
        'with_channels': with_channels,
        'without_channels': without_channels
    }


def print_summary(
    validation_result: Dict[str, Any],
    existing_data: Dict[str, List[str]],
    skip_confirmation: bool = False
) -> bool:
    """
    Stampa summary operazione e richiede conferma.
    
    Args:
        validation_result: Risultato da validate_and_split_dates()
        existing_data: Risultato da get_existing_dates()
        skip_confirmation: Se True, skip conferma interattiva
    
    Returns:
        True se operazione confermata, False altrimenti
    """
    print()
    print("=" * 80)
    print("  📊 REFRESH DATA GA4 - SUMMARY")
    print("=" * 80)
    print()
    
    # Info date range
    print(f"📅 Range date:")
    print(f"   • Inizio: {validation_result['start_date']}")
    print(f"   • Fine: {validation_result['end_date']}")
    print(f"   • Totale: {len(validation_result['all_dates'])} date")
    print()
    
    # Info dati esistenti da sovrascrivere
    dates_to_overwrite = existing_data['with_data']
    dates_to_create = existing_data['without_data']
    
    print(f"💾 Stato attuale database:")
    if dates_to_overwrite:
        print(f"   • Date da SOVRASCRIVERE: {len(dates_to_overwrite)}")
    if dates_to_create:
        print(f"   • Date da CREARE (nuove): {len(dates_to_create)}")
    print()
    
    # Info canali
    channels_available = validation_result['dates_with_channels']
    channels_unavailable = validation_result['dates_without_channels']
    
    print(f"📡 Sessioni per canale:")
    if channels_available:
        print(f"   • Date con canali disponibili (<=D-2): {len(channels_available)}")
    if channels_unavailable:
        print(f"   • Date SENZA canali (>D-2, troppo recenti): {len(channels_unavailable)}")
        print(f"     ⚠️  Queste date verranno aggiornate SOLO per metriche principali")
    print()
    
    # Warning sovrascrittura
    if dates_to_overwrite:
        print("⚠️  ATTENZIONE:")
        print(f"   Questa operazione SOVRASCRIVERÀ {len(dates_to_overwrite)} date esistenti")
        print(f"   in DB e Redis cache!")
        print()
    
    # Conferma
    if skip_confirmation:
        logger.info("Skip conferma (--skip-confirmation)")
        return True
    
    response = input("Procedere con refresh? [y/N]: ")
    print()
    
    if response.lower() == 'y':
        logger.info("Operazione confermata dall'utente")
        return True
    else:
        logger.info("Operazione annullata dall'utente")
        return False


def refresh_single_date(
    date: str,
    db: GA4Database,
    redis_cache: GA4RedisCache = None,
    include_channels: bool = True
) -> Dict[str, bool]:
    """
    Refresh dati per singola data (metriche + canali se disponibili).
    
    Args:
        date: Data da refreshare (YYYY-MM-DD)
        db: Istanza GA4Database
        redis_cache: Istanza GA4RedisCache (opzionale)
        include_channels: Se True, tenta estrazione canali (se data <= D-2)
    
    Returns:
        Dict con:
        - 'metrics_success': True se metriche salvate con successo
        - 'channels_success': True se canali salvati con successo
        - 'channels_attempted': True se tentata estrazione canali
    """
    result = {
        'metrics_success': False,
        'channels_success': False,
        'channels_attempted': False
    }
    
    try:
        # 1. Estrai dati principali
        logger.info(f"Estrazione metriche per {date}...")
        results, dates = extract_for_date(date)
        
        # 2. Salva in database (con replace=True per sovrascrivere)
        success = save_to_database(results, date, db, redis_cache, dates)
        
        if success:
            result['metrics_success'] = True
            logger.info(f"✓ Metriche salvate per {date}")
        else:
            logger.error(f"✗ Errore salvataggio metriche per {date}")
            return result
        
        # 3. Estrai sessioni canali se richiesto e disponibili
        if include_channels:
            result['channels_attempted'] = True
            logger.info(f"Estrazione sessioni canali per {date}...")
            
            # extract_sessions_channels_delayed gestisce già la validazione D-2
            channel_success = extract_sessions_channels_delayed(
                date,
                db,
                skip_validation=False  # Mantieni validazione D-2
            )
            
            if channel_success:
                result['channels_success'] = True
                logger.info(f"✓ Sessioni canali salvate per {date}")
            else:
                # Non è un errore critico (potrebbe essere data troppo recente)
                logger.debug(f"⚠ Sessioni canali non disponibili per {date}")
        
        return result
        
    except Exception as e:
        logger.error(f"✗ Errore refresh per {date}: {e}", exc_info=True)
        return result


# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Funzione principale per refresh dati GA4.
    """
    parser = argparse.ArgumentParser(
        description='Refresh (sovrascrive) dati GA4 esistenti nel database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  # Refresh ultimi 14 giorni (default)
  %(prog)s
  
  # Refresh ultimi 7 giorni
  %(prog)s --days 7
  
  # Refresh range specifico
  %(prog)s --start-date 2025-11-01 --end-date 2025-11-10
  
  # Skip conferma (per automazione)
  %(prog)s --days 14 --skip-confirmation
        """
    )
    
    # Opzioni per range date
    parser.add_argument(
        '--start-date',
        help='Data inizio (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        help='Data fine (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--days',
        type=int,
        help='Refresh ultimi N giorni (default: 14)'
    )
    
    # Opzioni aggiuntive
    parser.add_argument(
        '--db-path',
        default='data/ga4_data.db',
        help='Path database SQLite (default: data/ga4_data.db)'
    )
    parser.add_argument(
        '--skip-confirmation',
        action='store_true',
        help='Skip conferma interattiva (per automazione)'
    )
    
    args = parser.parse_args()
    
    # Header
    print()
    print("=" * 80)
    print("  🔄 REFRESH DATA GA4 - Aggiornamento Dati Esistenti")
    print("=" * 80)
    print()
    
    try:
        # 1. Calcola date range
        logger.info("=" * 70)
        logger.info("INIZIO REFRESH DATA GA4")
        logger.info("=" * 70)
        
        start_date, end_date = calculate_date_range(args)
        
        # 2. Valida e separa date
        validation_result = validate_and_split_dates(start_date, end_date)
        
        # 3. Setup database
        logger.info(f"Connessione database: {args.db_path}")
        db = GA4Database(args.db_path)
        
        # 4. Setup Redis (opzionale)
        try:
            redis_cache = GA4RedisCache()
            logger.info("✓ Redis cache connesso")
        except Exception as e:
            logger.warning(f"Redis non disponibile: {e}")
            redis_cache = None
        
        # 5. Verifica dati esistenti
        existing_data = get_existing_dates(db, validation_result['all_dates'])
        
        # 6. Mostra summary e richiedi conferma
        confirmed = print_summary(validation_result, existing_data, args.skip_confirmation)
        
        if not confirmed:
            print("Operazione annullata")
            db.close()
            if redis_cache:
                redis_cache.close()
            return 0
        
        # 7. Inizia refresh
        print("=" * 80)
        print("  🚀 INIZIO REFRESH")
        print("=" * 80)
        print()
        
        all_dates = validation_result['all_dates']
        dates_with_channels_available = set(validation_result['dates_with_channels'])
        
        # Contatori
        success_count = 0
        failed_count = 0
        channels_updated = 0
        channels_skipped = 0
        
        # Loop su tutte le date
        for i, date in enumerate(all_dates, 1):
            print(f"[{i}/{len(all_dates)}] Refreshing {date}...", end=" ")
            
            # Determina se includere canali
            include_channels = date in dates_with_channels_available
            
            # Refresh
            result = refresh_single_date(date, db, redis_cache, include_channels)
            
            if result['metrics_success']:
                success_count += 1
                status = "✓ OK"
                
                # Info canali
                if result['channels_attempted']:
                    if result['channels_success']:
                        channels_updated += 1
                        status += " + canali"
                    else:
                        channels_skipped += 1
                        status += " (canali skip)"
                
                print(status)
            else:
                failed_count += 1
                print("✗ FALLITO")
        
        print()
        
        # 8. Report finale
        print("=" * 80)
        print("  ✅ REFRESH COMPLETATO")
        print("=" * 80)
        print()
        
        print(f"📊 Risultati:")
        print(f"   • Metriche aggiornate: {success_count}/{len(all_dates)}")
        print(f"   • Falliti: {failed_count}/{len(all_dates)}")
        print()
        
        print(f"📡 Sessioni per canale:")
        print(f"   • Canali aggiornati: {channels_updated}")
        print(f"   • Canali skipped (troppo recenti): {channels_skipped}")
        print()
        
        # Statistiche database aggiornate
        stats = db.get_statistics()
        print(f"📈 Statistiche Database Aggiornate:")
        print(f"   • Record totali: {stats['record_count']}")
        print(f"   • Periodo: {stats['min_date']} → {stats['max_date']}")
        print(f"   • Media SWI: {stats['avg_swi_conversioni']:.0f}")
        print()
        
        # Info Redis cache
        if redis_cache:
            cache_info = redis_cache.get_cache_info()
            print(f"💾 Redis Cache:")
            print(f"   • Date in cache: {cache_info.get('cached_days', 0)}")
            print()
        
        # Chiudi connessioni
        db.close()
        if redis_cache:
            redis_cache.close()
        
        logger.info("=" * 70)
        logger.info(f"REFRESH COMPLETATO: {success_count} successi, {failed_count} falliti")
        logger.info("=" * 70)
        
        return 0 if failed_count == 0 else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Operazione interrotta dall'utente")
        logger.warning("Operazione interrotta da Ctrl+C")
        
        if 'db' in locals():
            db.close()
        if 'redis_cache' in locals() and redis_cache:
            redis_cache.close()
        
        return 130
    
    except Exception as e:
        logger.error(f"Errore durante refresh: {e}", exc_info=True)
        print(f"\n❌ ERRORE: {e}")
        print()
        print("📝 Controlla il log per dettagli: logs/refresh_data.log")
        print()
        
        if 'db' in locals():
            db.close()
        if 'redis_cache' in locals() and redis_cache:
            redis_cache.close()
        
        return 1


if __name__ == '__main__':
    sys.exit(main())

