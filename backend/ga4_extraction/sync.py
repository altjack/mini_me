"""
Database Sync Module per GA4.

Sincronizza tutte le tabelle satellite con daily_metrics come riferimento.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Configurazione tabelle da sincronizzare
SYNC_CONFIG = {
    'products_performance': {
        'delay_days': 0,
        'needs_swi': True,
        'extractor_func': 'giornaliero_prodotti',
    },
    'swi_by_commodity': {
        'delay_days': 0,
        'needs_swi': False,
        'extractor_func': 'SWI_per_commodity_type',
    },
    'sessions_by_channel': {
        'delay_days': 2,
        'needs_swi': False,
        'extractor_func': 'daily_sessions_channels',
    },
    'sessions_by_campaign': {
        'delay_days': 2,
        'needs_swi': False,
        'extractor_func': 'daily_sessions_campaigns',
    },
}


def sync_database(db, dry_run: bool = False, tables: Optional[list] = None) -> dict:
    """
    Sincronizza tutte le tabelle satellite con daily_metrics.

    Per ogni tabella non allineata:
    1. Identifica date mancanti
    2. Per ogni data mancante estrae dati da GA4 e li salva

    Args:
        db: Istanza GA4Database
        dry_run: Se True, solo report senza estrazioni effettive
        tables: Lista opzionale di tabelle da sincronizzare (default: tutte)

    Returns:
        Dict con risultati sync per ogni tabella
    """
    # Import lazy per evitare circular imports
    from .extraction import (
        get_ga_client,
        giornaliero_prodotti,
        SWI_per_commodity_type,
        daily_sessions_channels,
        daily_sessions_campaigns,
    )

    # Verifica stato attuale
    status = db.check_alignment_status()

    if status['summary']['all_aligned']:
        logger.info("Tutte le tabelle sono gi allineate")
        return {
            'success': True,
            'message': 'Tutte le tabelle sono allineate',
            'tables_synced': 0,
            'records_inserted': 0,
            'details': {}
        }

    # Filtra tabelle se specificato
    tables_to_sync = tables or list(SYNC_CONFIG.keys())

    result = {
        'success': True,
        'dry_run': dry_run,
        'tables_synced': 0,
        'records_inserted': 0,
        'errors': [],
        'details': {}
    }

    # Client GA4 (lazy init solo se necessario)
    client = None

    for table_name in tables_to_sync:
        table_status = status['tables'].get(table_name)

        if not table_status:
            logger.warning(f"Tabella {table_name} non trovata in status")
            continue

        if table_status['aligned']:
            logger.info(f"{table_name}: già allineata")
            result['details'][table_name] = {
                'status': 'aligned',
                'missing_count': 0,
                'synced_count': 0
            }
            continue

        missing_dates = table_status['missing_dates']
        config = SYNC_CONFIG[table_name]

        logger.info(f"{table_name}: {len(missing_dates)} date mancanti")

        if dry_run:
            result['details'][table_name] = {
                'status': 'dry_run',
                'missing_count': len(missing_dates),
                'missing_dates': missing_dates[:10],  # Prime 10 per brevità
                'synced_count': 0
            }
            continue

        # Inizializza client GA4 se necessario
        if client is None:
            try:
                client = get_ga_client()
            except Exception as e:
                logger.error(f"Errore autenticazione GA4: {e}")
                result['success'] = False
                result['errors'].append(f"Autenticazione GA4 fallita: {e}")
                return result

        # Sync delle date mancanti
        synced = 0
        errors = []

        for date in missing_dates:
            try:
                success = _sync_single_date(
                    db=db,
                    client=client,
                    table_name=table_name,
                    date=date,
                    config=config
                )

                if success:
                    synced += 1
                    logger.info(f"  ✓ {table_name} - {date}")
                else:
                    errors.append(f"{date}: sync fallito")
                    logger.warning(f"  ✗ {table_name} - {date}: sync fallito")

            except Exception as e:
                errors.append(f"{date}: {str(e)}")
                logger.error(f"  ✗ {table_name} - {date}: {e}")

        result['details'][table_name] = {
            'status': 'synced' if synced > 0 else 'failed',
            'missing_count': len(missing_dates),
            'synced_count': synced,
            'errors': errors if errors else None
        }

        result['tables_synced'] += 1 if synced > 0 else 0
        result['records_inserted'] += synced

        if errors:
            result['errors'].extend([f"{table_name}: {e}" for e in errors])

    result['success'] = len(result['errors']) == 0

    return result


def _sync_single_date(db, client, table_name: str, date: str, config: dict) -> bool:
    """
    Sincronizza una singola data per una tabella specifica.

    Args:
        db: Istanza GA4Database
        client: Client GA4 autenticato
        table_name: Nome tabella da sincronizzare
        date: Data da sincronizzare (YYYY-MM-DD)
        config: Configurazione tabella da SYNC_CONFIG

    Returns:
        True se sync riuscito, False altrimenti
    """
    from .extraction import (
        giornaliero_prodotti,
        SWI_per_commodity_type,
        daily_sessions_channels,
        daily_sessions_campaigns,
    )

    try:
        if table_name == 'products_performance':
            # Products richiede SWI totale
            metrics = db.get_metrics(date)
            if not metrics or metrics.get('swi_conversioni') is None:
                logger.warning(f"SWI mancante per {date}, skip products")
                return False

            total_swi = metrics['swi_conversioni']
            df = giornaliero_prodotti(client, date, total_swi)

            if df.empty:
                logger.warning(f"Nessun dato prodotto per {date}")
                return False

            # Prepara dati per insert
            products = []
            for _, row in df.iterrows():
                # Gestisce percentuale come stringa "XX.XX%"
                pct_str = row['Percentage']
                if isinstance(pct_str, str):
                    pct_val = float(pct_str.replace('%', ''))
                else:
                    pct_val = float(pct_str)

                products.append({
                    'product_name': row['Product'],
                    'total_conversions': float(row['Total']),
                    'percentage': pct_val
                })

            return db.insert_products(date, products, replace=True)

        elif table_name == 'swi_by_commodity':
            df = SWI_per_commodity_type(client, date)

            if df.empty:
                logger.warning(f"Nessun dato SWI commodity per {date}")
                return False

            commodities = []
            for _, row in df.iterrows():
                commodities.append({
                    'commodity_type': row['Commodity_Type'],
                    'conversions': int(row['Conversions'])
                })

            return db.insert_swi_by_commodity(date, commodities, replace=True)

        elif table_name == 'sessions_by_channel':
            df = daily_sessions_channels(client, date)

            if df.empty:
                logger.warning(f"Nessun dato channels per {date}")
                return False

            channels = []
            for _, row in df.iterrows():
                channels.append({
                    'channel': row['Channel'],
                    'commodity_sessions': int(row['Commodity_Sessions']),
                    'lucegas_sessions': int(row['LuceGas_Sessions'])
                })

            return db.insert_sessions_by_channel(date, channels, replace=True)

        elif table_name == 'sessions_by_campaign':
            df = daily_sessions_campaigns(client, date)

            if df.empty:
                logger.warning(f"Nessun dato campaigns per {date}")
                return False

            campaigns = []
            for _, row in df.iterrows():
                campaigns.append({
                    'campaign': row['Campaign'],
                    'commodity_sessions': int(row['Commodity_Sessions']),
                    'lucegas_sessions': int(row['LuceGas_Sessions'])
                })

            return db.insert_sessions_by_campaign(date, campaigns, replace=True)

        else:
            logger.error(f"Tabella non supportata: {table_name}")
            return False

    except Exception as e:
        logger.error(f"Errore sync {table_name} per {date}: {e}", exc_info=True)
        return False


def print_alignment_status(status: dict) -> None:
    """
    Stampa lo stato di allineamento in formato leggibile.

    Args:
        status: Output di db.check_alignment_status()
    """
    print("\n" + "=" * 70)
    print("STATO ALLINEAMENTO DATABASE")
    print("=" * 70)

    ref = status['reference']
    print(f"\nRiferimento: {ref['table']}")
    print(f"  Date: {ref['min_date']} → {ref['max_date']}")
    print(f"  Record: {ref['count']}")

    print(f"\nTabelle satellite:")
    for table_name, info in status['tables'].items():
        status_icon = "✓" if info['aligned'] else "✗"
        print(f"\n  {status_icon} {table_name}")
        print(f"    Delay: D-{info['delay_days']}")
        print(f"    Attese: {info['expected_count']} | Presenti: {info['actual_count']}")
        if info['missing_count'] > 0:
            print(f"    Mancanti: {info['missing_count']}")
            # Mostra prime 5 date mancanti
            sample = info['missing_dates'][:5]
            print(f"    Esempio: {', '.join(sample)}{'...' if len(info['missing_dates']) > 5 else ''}")

    print("\n" + "-" * 70)
    if status['summary']['all_aligned']:
        print("✓ Tutte le tabelle sono allineate")
    else:
        print(f"✗ Tabelle non allineate: {', '.join(status['summary']['tables_missing_data'])}")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    # Test standalone
    import sys
    sys.path.insert(0, '/Users/giacomomauri/Desktop/Automation/daily_report')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    from backend.ga4_extraction.database import GA4Database

    db = GA4Database()

    # Check status
    status = db.check_alignment_status()
    print_alignment_status(status)

    # Dry run
    print("\n--- DRY RUN ---")
    result = sync_database(db, dry_run=True)
    print(f"Result: {result}")

    db.close()
