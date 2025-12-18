#!/usr/bin/env python3
"""
Script per recuperare dati GA4 mancanti nel database.

Questo script:
1. Identifica date mancanti nel database
2. Estrae dati per quelle date
3. Salva in SQLite + Redis cache

Usage:
    # Recupera tutte le date mancanti negli ultimi 60 giorni
    uv run backfill_missing_dates.py

    # Recupera date mancanti in un range specifico
    uv run backfill_missing_dates.py --start-date 2025-11-01 --end-date 2025-11-10

    # Recupera una singola data
    uv run backfill_missing_dates.py --date 2025-11-05

    # Recupera anche sessioni per canale (D-2)
    uv run backfill_missing_dates.py --include-channels

    # Backfill incrementale per nuove variabili (usa orizzonte DB esistente)
    uv run backfill_missing_dates.py --incremental channels
    uv run backfill_missing_dates.py --incremental campaigns
    uv run backfill_missing_dates.py --incremental all --dry-run
"""

import sys
import os
import logging
import argparse
from datetime import datetime, timedelta
from typing import List, Set

# Aggiungi directory parent al path (per import da ga4_extraction)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.ga4_extraction.database import GA4Database
from backend.ga4_extraction.redis_cache import GA4RedisCache
from backend.ga4_extraction.extraction import extract_for_date, save_to_database, extract_sessions_channels_delayed, extract_sessions_campaigns_delayed

# Configurazione logging - usa /tmp su Vercel/Lambda (filesystem read-only)
# Check multipli: VERCEL, AWS_LAMBDA, o path in /var/task
_is_serverless = (
    os.getenv('VERCEL') or 
    os.getenv('AWS_LAMBDA_FUNCTION_NAME') or
    __file__.startswith('/var/task')
)
log_dir = '/tmp/logs' if _is_serverless else os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'backfill_missing_dates.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_missing_dates(db: GA4Database, start_date: str, end_date: str) -> List[str]:
    """
    Identifica date mancanti nel database in un range.
    
    Args:
        db: Istanza GA4Database
        start_date: Data inizio (YYYY-MM-DD)
        end_date: Data fine (YYYY-MM-DD)
    
    Returns:
        Lista di date mancanti (YYYY-MM-DD)
    """
    # Genera tutte le date nel range
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    all_dates = set()
    current = start
    while current <= end:
        all_dates.add(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    
    # Ottieni date presenti nel database
    stats = db.get_statistics()
    if stats['record_count'] == 0:
        logger.info("Database vuoto - tutte le date sono mancanti")
        return sorted(list(all_dates))
    
    # Query per ottenere tutte le date presenti
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT date FROM daily_metrics
        WHERE date BETWEEN ? AND ?
        ORDER BY date
    """, (start_date, end_date))
    
    existing_dates = set(row[0] for row in cursor.fetchall())
    
    # Calcola differenza
    missing_dates = all_dates - existing_dates
    
    return sorted(list(missing_dates))


def get_dates_missing_channels(db: GA4Database, start_date: str, end_date: str) -> List[str]:
    """
    Identifica date che hanno metriche ma mancano dati per canale.
    
    Args:
        db: Istanza GA4Database
        start_date: Data inizio (YYYY-MM-DD)
        end_date: Data fine (YYYY-MM-DD)
    
    Returns:
        Lista di date senza dati canale (YYYY-MM-DD)
    """
    cursor = db.conn.cursor()
    
    # Date con metriche ma senza dati canale
    cursor.execute("""
        SELECT dm.date
        FROM daily_metrics dm
        LEFT JOIN sessions_by_channel sc ON dm.date = sc.date
        WHERE dm.date BETWEEN ? AND ?
        GROUP BY dm.date
        HAVING COUNT(sc.id) = 0
        ORDER BY dm.date
    """, (start_date, end_date))
    
    dates_without_channels = [row[0] for row in cursor.fetchall()]
    
    return dates_without_channels


def get_dates_missing_campaigns(db: GA4Database, start_date: str, end_date: str) -> List[str]:
    """
    Identifica date che hanno metriche ma mancano dati per campagna.
    
    Args:
        db: Istanza GA4Database
        start_date: Data inizio (YYYY-MM-DD)
        end_date: Data fine (YYYY-MM-DD)
    
    Returns:
        Lista di date senza dati campagna (YYYY-MM-DD)
    """
    cursor = db.conn.cursor()
    
    # Date con metriche ma senza dati campagna
    cursor.execute("""
        SELECT dm.date
        FROM daily_metrics dm
        LEFT JOIN sessions_by_campaign sc ON dm.date = sc.date
        WHERE dm.date BETWEEN ? AND ?
        GROUP BY dm.date
        HAVING COUNT(sc.id) = 0
        ORDER BY dm.date
    """, (start_date, end_date))
    
    dates_without_campaigns = [row[0] for row in cursor.fetchall()]
    
    return dates_without_campaigns


def backfill_single_date(
    target_date: str,
    db: GA4Database,
    redis_cache: GA4RedisCache = None,
    include_channels: bool = False
) -> bool:
    """
    Recupera dati per una singola data.
    
    Args:
        target_date: Data da recuperare (YYYY-MM-DD)
        db: Istanza GA4Database
        redis_cache: Istanza GA4RedisCache (opzionale)
        include_channels: Se True, estrae anche sessioni per canale
    
    Returns:
        True se successo, False altrimenti
        
    Raises:
        Exception: Propaga eccezioni per debug in API
    """
    logger.info(f"Inizio backfill per {target_date}")
    
    # Estrai dati principali (eccezioni propagate per debug)
    results, dates = extract_for_date(target_date)
    
    # Salva in database
    success = save_to_database(results, target_date, db, redis_cache, dates)
    
    if not success:
        logger.error(f"✗ Errore salvataggio per {target_date}")
        raise Exception(f"Salvataggio fallito per {target_date}")
    
    logger.info(f"✓ Dati principali salvati per {target_date}")
    
    # Estrai sessioni per canale e campagna se richiesto
    if include_channels:
        logger.info(f"Estrazione sessioni per canale per {target_date}...")
        channel_success = extract_sessions_channels_delayed(target_date, db)
        if channel_success:
            logger.info(f"✓ Sessioni canale salvate per {target_date}")
        else:
            logger.warning(f"⚠ Sessioni canale non disponibili per {target_date} (ritardo GA4?)")
        
        logger.info(f"Estrazione sessioni per campagna per {target_date}...")
        campaign_success = extract_sessions_campaigns_delayed(target_date, db)
        if campaign_success:
            logger.info(f"✓ Sessioni campagna salvate per {target_date}")
        else:
            logger.warning(f"⚠ Sessioni campagna non disponibili per {target_date} (ritardo GA4?)")
    
    return True


def run_incremental_backfill(args) -> int:
    """
    Esegue backfill incrementale per nuove variabili.

    Usa l'orizzonte temporale esistente nel DB per backfillare
    solo le date che hanno metriche base ma mancano dati per l'extractor.

    Args:
        args: Argomenti CLI parsati

    Returns:
        Exit code (0 = successo, 1 = errore)
    """
    from backend.ga4_extraction.extractors.registry import list_extractors
    from backend.ga4_extraction.extractors.backfill import (
        incremental_backfill,
        backfill_all_extractors,
        get_db_date_range
    )

    extractor_name = args.incremental.lower()
    dry_run = args.dry_run

    # Setup database
    logger.info(f"Connessione database: {args.db_path}")
    db = GA4Database(args.db_path)

    try:
        # Mostra orizzonte temporale DB
        db_min, db_max = get_db_date_range(db)
        if db_min is None:
            print("❌ Database vuoto. Esegui prima un backfill completo delle metriche base.")
            return 1

        print(f"📅 Orizzonte temporale DB: {db_min} → {db_max}")
        print()

        # Backfill all extractors
        if extractor_name == 'all':
            print("🔄 Backfill incrementale per TUTTI gli extractors")
            print()

            if dry_run:
                print("🔍 [DRY RUN] Analisi date mancanti...\n")

            result = backfill_all_extractors(db=db, dry_run=dry_run)

            print()
            print("=" * 80)
            if dry_run:
                print("  🔍 RISULTATO DRY RUN")
            else:
                print("  ✅ BACKFILL COMPLETATO")
            print("=" * 80)
            print()

            for ext_name, ext_result in result.get('extractors', {}).items():
                if ext_result.get('error'):
                    print(f"❌ {ext_name}: {ext_result['error']}")
                elif dry_run:
                    total = ext_result.get('total_missing', 0)
                    print(f"📊 {ext_name}: {total} date da processare")
                    if total > 0 and 'dates_to_process' in ext_result:
                        dates = ext_result['dates_to_process']
                        preview = dates[:5]
                        print(f"   Prime date: {', '.join(preview)}")
                        if len(dates) > 5:
                            print(f"   ... e altre {len(dates) - 5}")
                else:
                    print(f"✓ {ext_name}: {ext_result.get('processed', 0)} processate, "
                          f"{ext_result.get('failed', 0)} fallite, "
                          f"{ext_result.get('skipped', 0)} skippate")

            print()
            print(f"📊 Totali: {result.get('total_processed', 0)} processate, "
                  f"{result.get('total_failed', 0)} fallite")

            return 0 if result.get('success', False) else 1

        # Backfill singolo extractor
        else:
            # Valida extractor
            available = [e['name'] for e in list_extractors()]
            if extractor_name not in available:
                print(f"❌ Extractor '{extractor_name}' non trovato.")
                print(f"   Disponibili: {', '.join(available)}")
                print(f"   Usa --list-extractors per dettagli")
                return 1

            print(f"🔄 Backfill incrementale per '{extractor_name}'")
            print()

            if dry_run:
                print("🔍 [DRY RUN] Analisi date mancanti...\n")

            # Usa start/end date se specificati, altrimenti usa orizzonte DB
            start_date = args.start_date if hasattr(args, 'start_date') else None
            end_date = args.end_date if hasattr(args, 'end_date') else None

            result = incremental_backfill(
                extractor_name=extractor_name,
                db=db,
                start_date=start_date,
                end_date=end_date,
                dry_run=dry_run
            )

            print()
            print("=" * 80)
            if dry_run:
                print("  🔍 RISULTATO DRY RUN")
            else:
                print("  ✅ BACKFILL COMPLETATO")
            print("=" * 80)
            print()

            if result.get('error'):
                print(f"❌ Errore: {result['error']}")
                return 1

            date_range = result.get('date_range', {})
            print(f"📅 Range analizzato: {date_range.get('start')} → {date_range.get('end')}")
            print(f"📊 Date mancanti trovate: {result.get('total_missing', 0)}")

            if dry_run:
                if result.get('total_missing', 0) > 0:
                    dates = result.get('dates_to_process', [])
                    print(f"\n📋 Date da processare:")
                    for d in dates[:10]:
                        print(f"   • {d}")
                    if len(dates) > 10:
                        print(f"   ... e altre {len(dates) - 10}")
                print(f"\n💡 Rimuovi --dry-run per eseguire il backfill")
            else:
                print(f"✓ Processate: {result.get('processed', 0)}")
                print(f"✗ Fallite: {result.get('failed', 0)}")
                print(f"⏭ Skippate: {result.get('skipped', 0)}")

                # Mostra dettagli errori
                details = result.get('details', [])
                errors = [d for d in details if not d.get('success') and not d.get('skipped')]
                if errors:
                    print(f"\n⚠️  Dettagli errori:")
                    for err in errors[:5]:
                        print(f"   • {err['date']}: {err.get('error', 'Errore sconosciuto')}")

            return 0 if result.get('success', False) else 1

    finally:
        db.close()


def main():
    """
    Funzione principale per backfill date mancanti.
    """
    parser = argparse.ArgumentParser(
        description='Recupera dati GA4 mancanti nel database'
    )
    
    # Opzioni per range date
    parser.add_argument(
        '--start-date',
        help='Data inizio (YYYY-MM-DD). Default: 60 giorni fa'
    )
    parser.add_argument(
        '--end-date',
        help='Data fine (YYYY-MM-DD). Default: ieri'
    )
    parser.add_argument(
        '--date',
        help='Singola data da recuperare (YYYY-MM-DD)'
    )
    
    # Opzioni aggiuntive
    parser.add_argument(
        '--include-channels',
        action='store_true',
        help='Include anche estrazione sessioni per canale (per date D-2)'
    )
    parser.add_argument(
        '--only-channels',
        action='store_true',
        help='Recupera SOLO sessioni per canale per date esistenti'
    )
    parser.add_argument(
        '--only-campaigns',
        action='store_true',
        help='Recupera SOLO sessioni per campagna per date esistenti'
    )
    parser.add_argument(
        '--db-path',
        default='data/ga4_data.db',
        help='Path database SQLite (default: data/ga4_data.db)'
    )

    # Opzioni backfill incrementale (nuove variabili)
    parser.add_argument(
        '--incremental',
        metavar='EXTRACTOR',
        help='Backfill incrementale per extractor specifico (channels, campaigns, all). '
             'Usa orizzonte temporale esistente nel DB (min_date → max_date - delay)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Mostra cosa verrebbe fatto senza eseguire (solo con --incremental)'
    )
    parser.add_argument(
        '--list-extractors',
        action='store_true',
        help='Mostra lista extractors disponibili'
    )

    args = parser.parse_args()

    # Header
    print("=" * 80)
    print("  📊 BACKFILL DATE MANCANTI - GA4 Data Recovery")
    print("=" * 80)
    print()

    # Modalità: lista extractors
    if args.list_extractors:
        from backend.ga4_extraction.extractors.registry import list_extractors
        extractors = list_extractors()
        print("📋 Extractors disponibili per backfill incrementale:\n")
        for ext in extractors:
            print(f"   • {ext['name']}: {ext['description']}")
            print(f"     Tabella: {ext['table_name']}, Ritardo GA4: D-{ext['ga4_delay_days']}")
            print()
        return 0

    # Modalità: backfill incrementale
    if args.incremental:
        return run_incremental_backfill(args)

    try:
        # Setup database
        logger.info(f"Connessione database: {args.db_path}")
        db = GA4Database(args.db_path)
        
        # Setup Redis (opzionale)
        try:
            redis_cache = GA4RedisCache()
            logger.info("✓ Redis cache connesso")
        except Exception as e:
            logger.warning(f"Redis non disponibile: {e}")
            redis_cache = None
        
        # Determina range date
        if args.date:
            # Singola data
            start_date = args.date
            end_date = args.date
            logger.info(f"Modalità singola data: {args.date}")
        else:
            # Range date
            # IMPORTANTE: end_date non deve essere più recente di D-2 per garantire dati GA4 disponibili
            if args.end_date:
                end_date = args.end_date
            else:
                end_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
            
            if args.start_date:
                start_date = args.start_date
            else:
                start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
            
            logger.info(f"Range date: {start_date} → {end_date}")
        
        print(f"📅 Range analisi: {start_date} → {end_date}")
        
        # Valida che end_date non sia troppo recente
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        max_date = (today - timedelta(days=2)).strftime('%Y-%m-%d')
        
        if end_date > max_date:
            print(f"⚠️  ATTENZIONE: end_date ({end_date}) è troppo recente")
            print(f"   GA4 richiede almeno 48h di ritardo per dati completi")
            print(f"   end_date automaticamente limitato a: {max_date} (D-2)")
            end_date = max_date
            logger.warning(f"end_date limitato a {max_date} per garantire dati GA4 disponibili")
            print()
        
        print()
        
        # Modalità: solo canali
        if args.only_channels:
            print("🔍 Ricerca date senza dati per canale...")
            dates_to_process = get_dates_missing_channels(db, start_date, end_date)
            
            if not dates_to_process:
                print("✓ Tutte le date hanno già dati per canale")
                db.close()
                if redis_cache:
                    redis_cache.close()
                return 0
            
            # Filtra date troppo recenti (< D-2)
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            min_date = (today - timedelta(days=2)).strftime('%Y-%m-%d')
            
            # Separa date valide e troppo recenti
            valid_dates = [d for d in dates_to_process if d <= min_date]
            recent_dates = [d for d in dates_to_process if d > min_date]
            
            if recent_dates:
                print(f"⚠️  ATTENZIONE: {len(recent_dates)} date troppo recenti (< D-2) escluse:")
                for date in recent_dates:
                    days_diff = (today - datetime.strptime(date, '%Y-%m-%d')).days
                    print(f"   • {date} (D-{days_diff}) - GA4 richiede almeno D-2")
                print()
            
            if not valid_dates:
                print("✗ Nessuna data valida per estrazione canali (tutte < D-2)")
                print(f"💡 Le date più recenti saranno disponibili da: {(today + timedelta(days=1)).strftime('%Y-%m-%d')}")
                db.close()
                if redis_cache:
                    redis_cache.close()
                return 0
            
            dates_to_process = valid_dates
            
            print(f"📋 Trovate {len(dates_to_process)} date valide senza dati canale:")
            for date in dates_to_process:
                print(f"   • {date}")
            print()
            
            # Conferma
            response = input("Procedere con estrazione sessioni per canale? [y/N]: ")
            if response.lower() != 'y':
                print("Operazione annullata")
                db.close()
                if redis_cache:
                    redis_cache.close()
                return 0
            
            print()
            print("=" * 80)
            print("  🚀 INIZIO ESTRAZIONE SESSIONI PER CANALE")
            print("=" * 80)
            print()
            
            success_count = 0
            failed_count = 0
            
            for i, date in enumerate(dates_to_process, 1):
                print(f"[{i}/{len(dates_to_process)}] Estrazione canali per {date}...")
                
                success = extract_sessions_channels_delayed(date, db)
                
                if success:
                    success_count += 1
                    print(f"✓ OK")
                else:
                    failed_count += 1
                    print(f"✗ FALLITO")
            
            print()
            print("=" * 80)
            print("  ✅ ESTRAZIONE COMPLETATA")
            print("=" * 80)
            print(f"✓ Successi: {success_count}")
            print(f"✗ Falliti: {failed_count}")
            print()
            
            db.close()
            if redis_cache:
                redis_cache.close()
            return 0 if failed_count == 0 else 1
        
        # Modalità: solo campagne
        elif args.only_campaigns:
                print("🔍 Ricerca date senza dati per campagna...")
                dates_to_process = get_dates_missing_campaigns(db, start_date, end_date)
                
                if not dates_to_process:
                    print("✓ Tutte le date hanno già dati per campagna")
                    db.close()
                    if redis_cache:
                        redis_cache.close()
                    return 0
                
                # Filtra date troppo recenti (< D-2)
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                min_date = (today - timedelta(days=2)).strftime('%Y-%m-%d')
                
                # Separa date valide e troppo recenti
                valid_dates = [d for d in dates_to_process if d <= min_date]
                recent_dates = [d for d in dates_to_process if d > min_date]
                
                if recent_dates:
                    print(f"⚠️  ATTENZIONE: {len(recent_dates)} date troppo recenti (< D-2) escluse:")
                    for date in recent_dates:
                        days_diff = (today - datetime.strptime(date, '%Y-%m-%d')).days
                        print(f"   • {date} (D-{days_diff}) - GA4 richiede almeno D-2")
                    print()
                
                if not valid_dates:
                    print("✗ Nessuna data valida per estrazione campagne (tutte < D-2)")
                    print(f"💡 Le date più recenti saranno disponibili da: {(today + timedelta(days=1)).strftime('%Y-%m-%d')}")
                    db.close()
                    if redis_cache:
                        redis_cache.close()
                    return 0
                
                dates_to_process = valid_dates
                
                print(f"📋 Trovate {len(dates_to_process)} date valide senza dati campagna:")
                for date in dates_to_process:
                    print(f"   • {date}")
                print()
                
                # Conferma
                response = input("Procedere con estrazione sessioni per campagna? [y/N]: ")
                if response.lower() != 'y':
                    print("Operazione annullata")
                    db.close()
                    if redis_cache:
                        redis_cache.close()
                    return 0
                
                print()
                print("=" * 80)
                print("  🚀 INIZIO ESTRAZIONE SESSIONI PER CAMPAGNA")
                print("=" * 80)
                print()
                
                success_count = 0
                failed_count = 0
                
                for i, date in enumerate(dates_to_process, 1):
                    print(f"[{i}/{len(dates_to_process)}] Estrazione campagne per {date}...", end=' ', flush=True)
                    
                    try:
                        campaign_success = extract_sessions_campaigns_delayed(date, db, skip_validation=True)
                        if campaign_success:
                            print(f"✓ OK")
                            success_count += 1
                        else:
                            print(f"✗ FALLITO (dati non disponibili)")
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"Errore estrazione campagne per {date}: {e}", exc_info=True)
                        print(f"✗ ERRORE: {e}")
                        failed_count += 1
                
                print()
                print("=" * 80)
                print("  ✅ ESTRAZIONE COMPLETATA")
                print("=" * 80)
                print(f"✓ Successi: {success_count}")
                print(f"✗ Falliti: {failed_count}")
                print()
                
                db.close()
                if redis_cache:
                    redis_cache.close()
                return 0 if failed_count == 0 else 1
        
        # Modalità: date mancanti
        else:
            print("🔍 Ricerca date mancanti nel database...")
            missing_dates = get_missing_dates(db, start_date, end_date)
            
            if not missing_dates:
                print("✓ Nessuna data mancante nel range specificato")
                
                # Controlla comunque se mancano dati canale o campagna
                if args.include_channels:
                    print()
                    print("🔍 Verifica dati per canale e campagna...")
                    dates_without_channels = get_dates_missing_channels(db, start_date, end_date)
                    dates_without_campaigns = get_dates_missing_campaigns(db, start_date, end_date)
                    
                    if dates_without_channels:
                        print(f"⚠ Trovate {len(dates_without_channels)} date senza dati canale")
                        print("   Usa --only-channels per recuperarli")
                    
                    if dates_without_campaigns:
                        print(f"⚠ Trovate {len(dates_without_campaigns)} date senza dati campagna")
                        print("   Usa --only-campaigns per recuperarli")
                
                db.close()
                if redis_cache:
                    redis_cache.close()
                return 0
            
            print(f"📋 Trovate {len(missing_dates)} date mancanti:")
            for date in missing_dates:
                print(f"   • {date}")
            print()
            
            # Conferma
            response = input(f"Procedere con backfill di {len(missing_dates)} date? [y/N]: ")
            if response.lower() != 'y':
                print("Operazione annullata")
                db.close()
                if redis_cache:
                    redis_cache.close()
                return 0
            
            print()
            print("=" * 80)
            print("  🚀 INIZIO BACKFILL")
            print("=" * 80)
            print()
            
            success_count = 0
            failed_count = 0
            
            for i, date in enumerate(missing_dates, 1):
                print(f"[{i}/{len(missing_dates)}] Backfill per {date}...")
                
                success = backfill_single_date(
                    date,
                    db,
                    redis_cache,
                    include_channels=args.include_channels
                )
                
                if success:
                    success_count += 1
                    print(f"✓ OK")
                else:
                    failed_count += 1
                    print(f"✗ FALLITO")
                
                print()
        
        # Riepilogo finale
        print()
        print("=" * 80)
        print("  ✅ BACKFILL COMPLETATO")
        print("=" * 80)
        print()
        print(f"📊 Risultati:")
        print(f"   • Successo: {success_count}")
        print(f"   • Falliti: {failed_count}")
        print(f"   • Totale: {success_count + failed_count}")
        print()
        
        # Mostra statistiche database aggiornate
        stats = db.get_statistics()
        print(f"📈 Statistiche Database:")
        print(f"   • Record totali: {stats['record_count']}")
        print(f"   • Periodo: {stats['min_date']} → {stats['max_date']}")
        print(f"   • Media SWI: {stats['avg_swi_conversioni']:.0f}")
        print()
        
        # Chiudi connessioni
        db.close()
        if redis_cache:
            redis_cache.close()
        
        logger.info(f"Backfill completato: {success_count} successi, {failed_count} falliti")
        
        return 0 if failed_count == 0 else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Operazione interrotta dall'utente")
        if 'db' in locals():
            db.close()
        if 'redis_cache' in locals() and redis_cache:
            redis_cache.close()
        return 130
    
    except Exception as e:
        logger.error(f"Errore durante backfill: {e}", exc_info=True)
        print(f"\n❌ ERRORE: {e}")
        print()
        print("📝 Controlla il log per dettagli: backfill_missing_dates.log")
        
        if 'db' in locals():
            db.close()
        if 'redis_cache' in locals() and redis_cache:
            redis_cache.close()
        
        return 1


if __name__ == '__main__':
    sys.exit(main())

