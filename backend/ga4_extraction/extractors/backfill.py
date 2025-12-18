"""
Backfill incrementale per Extractors GA4.

Fornisce funzioni per eseguire backfill di nuove variabili usando
l'orizzonte temporale esistente nel database.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

from .registry import get_extractor, list_extractors
from .base import BaseExtractor

logger = logging.getLogger(__name__)


def get_db_date_range(db) -> tuple:
    """
    Ottiene l'orizzonte temporale dei dati esistenti nel database.

    Returns:
        Tuple (min_date: str, max_date: str) o (None, None) se DB vuoto
    """
    stats = db.get_statistics()

    if stats['record_count'] == 0:
        return None, None

    return stats['min_date'], stats['max_date']


def incremental_backfill(
    extractor_name: str,
    db=None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    dry_run: bool = False,
    skip_validation: bool = False
) -> Dict[str, Any]:
    """
    Esegue backfill incrementale per un extractor specifico.

    Logica:
    1. Se start_date/end_date non specificati, usa orizzonte DB (min_date → max_date - delay)
    2. Trova date mancanti per l'extractor (hanno metriche base ma non dati extractor)
    3. Estrae e salva dati solo per quelle date

    Args:
        extractor_name: Nome dell'extractor registrato (es. 'channels', 'campaigns')
        db: Istanza GA4Database (opzionale, crea nuova se non fornita)
        start_date: Data inizio override (YYYY-MM-DD). Se None, usa min_date dal DB
        end_date: Data fine override (YYYY-MM-DD). Se None, usa max_date - delay dal DB
        dry_run: Se True, mostra solo cosa farebbe senza eseguire
        skip_validation: Se True, salta validazione date (es. per date storiche)

    Returns:
        Dict con risultati:
        {
            'success': bool,
            'extractor': str,
            'date_range': {'start': str, 'end': str},
            'total_missing': int,
            'processed': int,
            'failed': int,
            'skipped': int,
            'details': [{'date': str, 'success': bool, 'error': str|None}, ...]
        }
    """
    # Ottieni extractor
    extractor = get_extractor(extractor_name)
    if not extractor:
        available = [e['name'] for e in list_extractors()]
        return {
            'success': False,
            'error': f"Extractor '{extractor_name}' non trovato. Disponibili: {available}",
            'extractor': extractor_name,
            'processed': 0,
            'failed': 0
        }

    # Setup database
    owns_db = db is None
    if owns_db:
        from backend.ga4_extraction.database import GA4Database
        db = GA4Database()

    try:
        # Determina orizzonte temporale
        if start_date is None or end_date is None:
            db_min, db_max = get_db_date_range(db)

            if db_min is None:
                return {
                    'success': False,
                    'error': "Database vuoto. Esegui prima un backfill completo.",
                    'extractor': extractor_name,
                    'processed': 0,
                    'failed': 0
                }

            if start_date is None:
                start_date = db_min

            if end_date is None:
                # Applica ritardo GA4
                max_date_obj = datetime.strptime(db_max, '%Y-%m-%d')
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                delay_limit = today - timedelta(days=extractor.ga4_delay_days)

                # end_date è il minore tra db_max e (oggi - delay)
                if max_date_obj > delay_limit:
                    end_date = delay_limit.strftime('%Y-%m-%d')
                else:
                    end_date = db_max

        logger.info(f"Backfill incrementale '{extractor_name}': {start_date} → {end_date}")

        # Valida range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')

        if start_dt > end_dt:
            return {
                'success': False,
                'error': f"Range invalido: start_date ({start_date}) > end_date ({end_date})",
                'extractor': extractor_name,
                'processed': 0,
                'failed': 0
            }

        # Trova date mancanti
        missing_dates = extractor.get_dates_missing(db, start_date, end_date)

        logger.info(f"Trovate {len(missing_dates)} date mancanti per '{extractor_name}'")

        if not missing_dates:
            return {
                'success': True,
                'extractor': extractor_name,
                'date_range': {'start': start_date, 'end': end_date},
                'total_missing': 0,
                'processed': 0,
                'failed': 0,
                'skipped': 0,
                'message': "Nessuna data mancante nel range specificato",
                'details': []
            }

        # Dry run: ritorna solo info
        if dry_run:
            return {
                'success': True,
                'dry_run': True,
                'extractor': extractor_name,
                'date_range': {'start': start_date, 'end': end_date},
                'total_missing': len(missing_dates),
                'dates_to_process': missing_dates,
                'message': f"Dry run: {len(missing_dates)} date verrebbero processate"
            }

        # Esegui estrazione
        from backend.ga4_extraction.extraction import get_ga_client

        client = get_ga_client()
        details = []
        processed = 0
        failed = 0
        skipped = 0

        for date in missing_dates:
            # Valida data (se non skip)
            if not skip_validation:
                is_valid, msg = extractor.validate_date(date)
                if not is_valid:
                    logger.warning(f"Skip {date}: {msg}")
                    details.append({'date': date, 'success': False, 'error': msg, 'skipped': True})
                    skipped += 1
                    continue

            try:
                # Estrai
                data = extractor.extract(client, date)

                if not data:
                    logger.warning(f"Nessun dato estratto per {date}")
                    details.append({'date': date, 'success': False, 'error': 'Nessun dato disponibile'})
                    failed += 1
                    continue

                # Salva
                success = extractor.save(db, date, data)

                if success:
                    logger.info(f"✓ {extractor_name} salvato per {date}: {len(data)} record")
                    details.append({'date': date, 'success': True, 'records': len(data)})
                    processed += 1
                else:
                    logger.error(f"✗ Errore salvataggio {extractor_name} per {date}")
                    details.append({'date': date, 'success': False, 'error': 'Errore salvataggio'})
                    failed += 1

            except Exception as e:
                logger.error(f"✗ Errore estrazione {extractor_name} per {date}: {e}")
                details.append({'date': date, 'success': False, 'error': str(e)})
                failed += 1

        return {
            'success': failed == 0,
            'extractor': extractor_name,
            'date_range': {'start': start_date, 'end': end_date},
            'total_missing': len(missing_dates),
            'processed': processed,
            'failed': failed,
            'skipped': skipped,
            'details': details
        }

    finally:
        if owns_db and db:
            db.close()


def backfill_all_extractors(
    db=None,
    dry_run: bool = False,
    skip_validation: bool = False
) -> Dict[str, Any]:
    """
    Esegue backfill incrementale per TUTTI gli extractors registrati.

    Args:
        db: Istanza GA4Database (opzionale)
        dry_run: Se True, mostra solo cosa farebbe
        skip_validation: Se True, salta validazione date

    Returns:
        Dict con risultati per ogni extractor
    """
    extractors = list_extractors()
    results = {}

    for ext_info in extractors:
        name = ext_info['name']
        logger.info(f"Backfill incrementale per '{name}'...")

        result = incremental_backfill(
            extractor_name=name,
            db=db,
            dry_run=dry_run,
            skip_validation=skip_validation
        )
        results[name] = result

    # Calcola totali
    total_processed = sum(r.get('processed', 0) for r in results.values())
    total_failed = sum(r.get('failed', 0) for r in results.values())

    return {
        'success': total_failed == 0,
        'total_processed': total_processed,
        'total_failed': total_failed,
        'extractors': results
    }


if __name__ == '__main__':
    # Test standalone
    import sys
    logging.basicConfig(level=logging.INFO)

    print("Extractors disponibili:")
    for ext in list_extractors():
        print(f"  - {ext['name']}: {ext['description']}")

    print("\nTest dry run per 'channels'...")
    result = incremental_backfill('channels', dry_run=True)
    print(f"Risultato: {result}")
