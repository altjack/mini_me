#!/usr/bin/env python3
"""
Script per migrare i dati da SQLite locale a PostgreSQL.
Esegue:
1. Crea le tabelle su PostgreSQL (se non esistono)
2. Legge tutti i dati da SQLite
3. Inserisce i dati in PostgreSQL
"""

import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
import sys

# Configurazione
SQLITE_PATH = Path(__file__).parent.parent.parent / "data" / "ga4_data.db"
POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "daily_report",
    "user": "daily_report_user",
    "password": "3x6qNZnRPPy7pMteYxJnzMibF8lByII"
}

def get_sqlite_connection():
    """Connessione a SQLite"""
    if not SQLITE_PATH.exists():
        print(f"ERRORE: Database SQLite non trovato: {SQLITE_PATH}")
        sys.exit(1)
    return sqlite3.connect(str(SQLITE_PATH))

def get_postgres_connection():
    """Connessione a PostgreSQL"""
    return psycopg2.connect(**POSTGRES_CONFIG)

def create_postgres_schema(pg_conn):
    """Crea le tabelle su PostgreSQL"""
    schema_sql = """
    -- daily_metrics
    CREATE TABLE IF NOT EXISTS daily_metrics (
        date DATE PRIMARY KEY,
        extraction_timestamp TIMESTAMP NOT NULL,
        sessioni_commodity INTEGER NOT NULL,
        sessioni_lucegas INTEGER NOT NULL,
        swi_conversioni INTEGER NOT NULL,
        cr_commodity REAL NOT NULL,
        cr_lucegas REAL NOT NULL,
        cr_canalizzazione REAL NOT NULL,
        start_funnel INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(date DESC);

    -- products_performance
    CREATE TABLE IF NOT EXISTS products_performance (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL,
        product_name TEXT NOT NULL,
        total_conversions REAL NOT NULL,
        percentage REAL NOT NULL,
        UNIQUE(date, product_name)
    );
    CREATE INDEX IF NOT EXISTS idx_products_date ON products_performance(date DESC);
    CREATE INDEX IF NOT EXISTS idx_products_name ON products_performance(product_name);

    -- sessions_by_channel
    CREATE TABLE IF NOT EXISTS sessions_by_channel (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL,
        channel TEXT NOT NULL,
        commodity_sessions INTEGER NOT NULL DEFAULT 0,
        lucegas_sessions INTEGER NOT NULL DEFAULT 0,
        UNIQUE(date, channel)
    );
    CREATE INDEX IF NOT EXISTS idx_channel_date ON sessions_by_channel(date DESC);
    CREATE INDEX IF NOT EXISTS idx_channel_name ON sessions_by_channel(channel);

    -- sessions_by_campaign
    CREATE TABLE IF NOT EXISTS sessions_by_campaign (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL,
        campaign TEXT NOT NULL,
        commodity_sessions INTEGER NOT NULL DEFAULT 0,
        lucegas_sessions INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(date, campaign)
    );
    CREATE INDEX IF NOT EXISTS idx_campaign_date ON sessions_by_campaign(date DESC);
    CREATE INDEX IF NOT EXISTS idx_campaign_name ON sessions_by_campaign(campaign);

    -- _migrations tracking
    CREATE TABLE IF NOT EXISTS _migrations (
        version TEXT PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        checksum TEXT
    );
    """
    with pg_conn.cursor() as cur:
        cur.execute(schema_sql)
    pg_conn.commit()
    print("✓ Schema PostgreSQL creato/verificato")

def migrate_daily_metrics(sqlite_conn, pg_conn):
    """Migra daily_metrics"""
    sqlite_cur = sqlite_conn.cursor()
    sqlite_cur.execute("SELECT * FROM daily_metrics ORDER BY date")
    rows = sqlite_cur.fetchall()

    if not rows:
        print("  Nessun dato in daily_metrics")
        return 0

    with pg_conn.cursor() as pg_cur:
        # Pulisci e inserisci
        pg_cur.execute("DELETE FROM daily_metrics")
        insert_sql = """
            INSERT INTO daily_metrics
            (date, extraction_timestamp, sessioni_commodity, sessioni_lucegas,
             swi_conversioni, cr_commodity, cr_lucegas, cr_canalizzazione, start_funnel)
            VALUES %s
            ON CONFLICT (date) DO UPDATE SET
                extraction_timestamp = EXCLUDED.extraction_timestamp,
                sessioni_commodity = EXCLUDED.sessioni_commodity,
                sessioni_lucegas = EXCLUDED.sessioni_lucegas,
                swi_conversioni = EXCLUDED.swi_conversioni,
                cr_commodity = EXCLUDED.cr_commodity,
                cr_lucegas = EXCLUDED.cr_lucegas,
                cr_canalizzazione = EXCLUDED.cr_canalizzazione,
                start_funnel = EXCLUDED.start_funnel
        """
        execute_values(pg_cur, insert_sql, rows)
    pg_conn.commit()
    print(f"✓ daily_metrics: {len(rows)} record migrati")
    return len(rows)

def migrate_products_performance(sqlite_conn, pg_conn):
    """Migra products_performance"""
    sqlite_cur = sqlite_conn.cursor()
    sqlite_cur.execute("SELECT date, product_name, total_conversions, percentage FROM products_performance ORDER BY date")
    rows = sqlite_cur.fetchall()

    if not rows:
        print("  Nessun dato in products_performance")
        return 0

    with pg_conn.cursor() as pg_cur:
        pg_cur.execute("DELETE FROM products_performance")
        insert_sql = """
            INSERT INTO products_performance (date, product_name, total_conversions, percentage)
            VALUES %s
            ON CONFLICT (date, product_name) DO UPDATE SET
                total_conversions = EXCLUDED.total_conversions,
                percentage = EXCLUDED.percentage
        """
        execute_values(pg_cur, insert_sql, rows)
    pg_conn.commit()
    print(f"✓ products_performance: {len(rows)} record migrati")
    return len(rows)

def migrate_sessions_by_channel(sqlite_conn, pg_conn):
    """Migra sessions_by_channel"""
    sqlite_cur = sqlite_conn.cursor()
    sqlite_cur.execute("SELECT date, channel, commodity_sessions, lucegas_sessions FROM sessions_by_channel ORDER BY date")
    rows = sqlite_cur.fetchall()

    if not rows:
        print("  Nessun dato in sessions_by_channel")
        return 0

    with pg_conn.cursor() as pg_cur:
        pg_cur.execute("DELETE FROM sessions_by_channel")
        insert_sql = """
            INSERT INTO sessions_by_channel (date, channel, commodity_sessions, lucegas_sessions)
            VALUES %s
            ON CONFLICT (date, channel) DO UPDATE SET
                commodity_sessions = EXCLUDED.commodity_sessions,
                lucegas_sessions = EXCLUDED.lucegas_sessions
        """
        execute_values(pg_cur, insert_sql, rows)
    pg_conn.commit()
    print(f"✓ sessions_by_channel: {len(rows)} record migrati")
    return len(rows)

def migrate_sessions_by_campaign(sqlite_conn, pg_conn):
    """Migra sessions_by_campaign"""
    sqlite_cur = sqlite_conn.cursor()

    # Verifica se la tabella esiste in SQLite
    sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions_by_campaign'")
    if not sqlite_cur.fetchone():
        print("  Tabella sessions_by_campaign non esiste in SQLite")
        return 0

    sqlite_cur.execute("SELECT date, campaign, commodity_sessions, lucegas_sessions FROM sessions_by_campaign ORDER BY date")
    rows = sqlite_cur.fetchall()

    if not rows:
        print("  Nessun dato in sessions_by_campaign")
        return 0

    with pg_conn.cursor() as pg_cur:
        pg_cur.execute("DELETE FROM sessions_by_campaign")
        insert_sql = """
            INSERT INTO sessions_by_campaign (date, campaign, commodity_sessions, lucegas_sessions)
            VALUES %s
            ON CONFLICT (date, campaign) DO UPDATE SET
                commodity_sessions = EXCLUDED.commodity_sessions,
                lucegas_sessions = EXCLUDED.lucegas_sessions
        """
        execute_values(pg_cur, insert_sql, rows)
    pg_conn.commit()
    print(f"✓ sessions_by_campaign: {len(rows)} record migrati")
    return len(rows)

def main():
    print("=" * 60)
    print("MIGRAZIONE SQLite → PostgreSQL")
    print("=" * 60)
    print(f"SQLite source: {SQLITE_PATH}")
    print(f"PostgreSQL target: {POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}/{POSTGRES_CONFIG['database']}")
    print()

    # Connessioni
    print("Connessione ai database...")
    sqlite_conn = get_sqlite_connection()
    pg_conn = get_postgres_connection()
    print("✓ Connessioni stabilite")
    print()

    # Crea schema
    print("Creazione schema PostgreSQL...")
    create_postgres_schema(pg_conn)
    print()

    # Migrazione dati
    print("Migrazione dati...")
    total = 0
    total += migrate_daily_metrics(sqlite_conn, pg_conn)
    total += migrate_products_performance(sqlite_conn, pg_conn)
    total += migrate_sessions_by_channel(sqlite_conn, pg_conn)
    total += migrate_sessions_by_campaign(sqlite_conn, pg_conn)

    print()
    print("=" * 60)
    print(f"MIGRAZIONE COMPLETATA: {total} record totali migrati")
    print("=" * 60)

    # Cleanup
    sqlite_conn.close()
    pg_conn.close()

if __name__ == "__main__":
    main()
