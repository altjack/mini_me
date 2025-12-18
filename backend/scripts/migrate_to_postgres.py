#!/usr/bin/env python3
"""
Script di migrazione dati da SQLite locale a PostgreSQL (Render).

Uso:
    # Export da SQLite a JSON (esegui in locale)
    python scripts/migrate_to_postgres.py export
    
    # Import da JSON a PostgreSQL (esegui con DATABASE_URL configurato)
    DATABASE_URL=postgres://... python scripts/migrate_to_postgres.py import
    
    # Migrazione diretta (richiede accesso a entrambi i DB)
    DATABASE_URL=postgres://... python scripts/migrate_to_postgres.py migrate

Note:
    - L'export crea file JSON nella cartella data/export/
    - L'import legge da data/export/ e inserisce in PostgreSQL
    - Esegui prima 'export' in locale, poi 'import' dopo deploy
"""

import os
import sys
import json
import sqlite3
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Aggiungi root al path per import
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.ga4_extraction.database import GA4Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Directory per export
EXPORT_DIR = Path(__file__).parent.parent / 'data' / 'export'


def export_sqlite_to_json(db_path: str = 'data/ga4_data.db'):
    """
    Esporta tutti i dati da SQLite a file JSON.
    
    Args:
        db_path: Percorso database SQLite
    """
    logger.info(f"Export da SQLite: {db_path}")
    
    # Crea directory export
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Connessione SQLite
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Export daily_metrics
    cursor.execute("SELECT * FROM daily_metrics ORDER BY date")
    metrics = [dict(row) for row in cursor.fetchall()]
    
    with open(EXPORT_DIR / 'daily_metrics.json', 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2, default=str)
    logger.info(f"  ✓ daily_metrics: {len(metrics)} record")
    
    # Export products_performance
    cursor.execute("SELECT * FROM products_performance ORDER BY date, id")
    products = [dict(row) for row in cursor.fetchall()]
    
    with open(EXPORT_DIR / 'products_performance.json', 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, default=str)
    logger.info(f"  ✓ products_performance: {len(products)} record")
    
    # Export sessions_by_channel
    cursor.execute("SELECT * FROM sessions_by_channel ORDER BY date, id")
    sessions = [dict(row) for row in cursor.fetchall()]
    
    with open(EXPORT_DIR / 'sessions_by_channel.json', 'w', encoding='utf-8') as f:
        json.dump(sessions, f, indent=2, default=str)
    logger.info(f"  ✓ sessions_by_channel: {len(sessions)} record")
    
    conn.close()
    
    logger.info(f"\n✓ Export completato in: {EXPORT_DIR}")
    logger.info("  Ora puoi copiare questi file e fare import su PostgreSQL")


def import_json_to_postgres():
    """
    Importa dati da JSON a PostgreSQL.
    
    Richiede DATABASE_URL environment variable configurata.
    """
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL non configurata!")
        logger.error("Uso: DATABASE_URL=postgres://... python migrate_to_postgres.py import")
        sys.exit(1)
    
    logger.info("Import in PostgreSQL...")
    
    # Verifica file export esistano
    if not EXPORT_DIR.exists():
        logger.error(f"Directory export non trovata: {EXPORT_DIR}")
        logger.error("Esegui prima: python migrate_to_postgres.py export")
        sys.exit(1)
    
    # Connessione PostgreSQL tramite GA4Database
    db = GA4Database()  # Usa DATABASE_URL automaticamente
    
    # Crea schema
    logger.info("  Creazione schema...")
    db.create_schema()
    
    # Import daily_metrics
    metrics_file = EXPORT_DIR / 'daily_metrics.json'
    if metrics_file.exists():
        with open(metrics_file, 'r', encoding='utf-8') as f:
            metrics = json.load(f)
        
        imported = 0
        for m in metrics:
            success = db.insert_daily_metrics(m['date'], {
                'sessioni_commodity': m['sessioni_commodity'],
                'sessioni_lucegas': m['sessioni_lucegas'],
                'swi_conversioni': m['swi_conversioni'],
                'cr_commodity': m['cr_commodity'],
                'cr_lucegas': m['cr_lucegas'],
                'cr_canalizzazione': m['cr_canalizzazione'],
                'start_funnel': m['start_funnel']
            })
            if success:
                imported += 1
        
        logger.info(f"  ✓ daily_metrics: {imported}/{len(metrics)} record importati")
    
    # Import products_performance
    products_file = EXPORT_DIR / 'products_performance.json'
    if products_file.exists():
        with open(products_file, 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        # Raggruppa per data
        by_date = {}
        for p in products:
            date = p['date']
            if date not in by_date:
                by_date[date] = []
            by_date[date].append({
                'product_name': p['product_name'],
                'total_conversions': p['total_conversions'],
                'percentage': p['percentage']
            })
        
        imported = 0
        for date, prods in by_date.items():
            success = db.insert_products(date, prods)
            if success:
                imported += len(prods)
        
        logger.info(f"  ✓ products_performance: {imported}/{len(products)} record importati")
    
    # Import sessions_by_channel
    sessions_file = EXPORT_DIR / 'sessions_by_channel.json'
    if sessions_file.exists():
        with open(sessions_file, 'r', encoding='utf-8') as f:
            sessions = json.load(f)
        
        # Raggruppa per data
        by_date = {}
        for s in sessions:
            date = s['date']
            if date not in by_date:
                by_date[date] = []
            by_date[date].append({
                'channel': s['channel'],
                'commodity_sessions': s['commodity_sessions'],
                'lucegas_sessions': s['lucegas_sessions']
            })
        
        imported = 0
        for date, chans in by_date.items():
            success = db.insert_sessions_by_channel(date, chans)
            if success:
                imported += len(chans)
        
        logger.info(f"  ✓ sessions_by_channel: {imported}/{len(sessions)} record importati")
    
    db.close()
    logger.info("\n✓ Import completato!")


def migrate_direct(sqlite_path: str = 'data/ga4_data.db'):
    """
    Migrazione diretta da SQLite a PostgreSQL (richiede accesso a entrambi).
    
    Args:
        sqlite_path: Percorso database SQLite locale
    """
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL non configurata!")
        sys.exit(1)
    
    logger.info(f"Migrazione diretta: {sqlite_path} → PostgreSQL")
    
    # Step 1: Export
    export_sqlite_to_json(sqlite_path)
    
    # Step 2: Import
    import_json_to_postgres()
    
    logger.info("\n✓ Migrazione completata!")


def verify_postgres():
    """Verifica contenuto database PostgreSQL."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL non configurata!")
        sys.exit(1)
    
    db = GA4Database()
    stats = db.get_statistics()
    
    print("\n📊 Statistiche PostgreSQL:")
    print(f"   Record totali: {stats.get('record_count', 0)}")
    print(f"   Data minima: {stats.get('min_date', 'N/A')}")
    print(f"   Data massima: {stats.get('max_date', 'N/A')}")
    
    db.close()


def main():
    parser = argparse.ArgumentParser(
        description='Migrazione dati SQLite → PostgreSQL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  # Step 1: Export da SQLite locale
  python scripts/migrate_to_postgres.py export
  
  # Step 2: Import in PostgreSQL (dopo deploy su Render)
  DATABASE_URL=postgres://user:pass@host/db python scripts/migrate_to_postgres.py import
  
  # Verifica dati importati
  DATABASE_URL=postgres://... python scripts/migrate_to_postgres.py verify
        """
    )
    
    parser.add_argument(
        'action',
        choices=['export', 'import', 'migrate', 'verify'],
        help='Azione da eseguire'
    )
    
    parser.add_argument(
        '--db-path',
        default='data/ga4_data.db',
        help='Percorso database SQLite (default: data/ga4_data.db)'
    )
    
    args = parser.parse_args()
    
    if args.action == 'export':
        export_sqlite_to_json(args.db_path)
    elif args.action == 'import':
        import_json_to_postgres()
    elif args.action == 'migrate':
        migrate_direct(args.db_path)
    elif args.action == 'verify':
        verify_postgres()


if __name__ == '__main__':
    main()

