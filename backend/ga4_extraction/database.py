#!/usr/bin/env python3
"""
Database Manager per dati GA4.

Supporta sia SQLite (sviluppo locale) che PostgreSQL (produzione/staging).
La scelta del database è automatica basata sulla variabile DATABASE_URL.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from urllib.parse import urlparse
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# =============================================================================
# DATABASE FACTORY
# =============================================================================

def get_database_connection(db_url: Optional[str] = None):
    """
    Factory per ottenere connessione database.
    
    Args:
        db_url: URL database (es. postgres://... o sqlite:///path)
                Se None, usa DATABASE_URL env var o fallback SQLite locale
    
    Returns:
        Connessione database appropriata
    """
    url = db_url or os.getenv('DATABASE_URL')
    
    if url and url.startswith(('postgres://', 'postgresql://')):
        # PostgreSQL (Render, Heroku, etc.)
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Render usa postgres:// ma psycopg2 vuole postgresql://
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)

        # Neon e molti provider serverless richiedono SSL; forza solo se non locale
        if 'sslmode=' not in url and 'localhost' not in url and '127.0.0.1' not in url:
            separator = '&' if '?' in url else '?'
            url = f"{url}{separator}sslmode=require"
        
        conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
        return conn, 'postgresql'
    else:
        # SQLite (sviluppo locale)
        import sqlite3
        db_path = url.replace('sqlite:///', '') if url else 'data/ga4_data.db'
        
        # Crea directory se non esiste
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn, 'sqlite'


class GA4Database:
    """Manager per database delle metriche GA4 (SQLite/PostgreSQL)."""

    def __init__(self, db_path: Optional[str] = None, conn=None, owns_connection: bool = True, run_migrations: bool = True):
        """
        Inizializza connessione al database.

        Args:
            db_path: Percorso file database SQLite o URL PostgreSQL.
                     Se None, usa DATABASE_URL env var o default SQLite.
            conn: Connessione esistente da riutilizzare (per pooling).
                  Se fornita, db_path viene ignorato.
            owns_connection: Se False, la connessione non verrà chiusa in close().
                           Utile quando si usa connection pooling.
            run_migrations: Se True, esegue migrations pendenti all'avvio (default: True)
        """
        self._owns_connection = owns_connection

        if conn is not None:
            # Usa connessione fornita (da pool)
            self.conn = conn
            self.db_path = "pooled"
            # Detect db type dalla connessione
            # PostgreSQL connections have 'server_version', SQLite don't
            try:
                import psycopg2
                self.db_type = 'postgresql' if isinstance(conn, psycopg2.extensions.connection) else 'sqlite'
            except ImportError:
                # Se psycopg2 non è installato, assume SQLite
                self.db_type = 'sqlite'
            logger.debug(f"Database using pooled connection ({self.db_type})")
        else:
            # Crea nuova connessione (comportamento originale)
            # Controlla se è un URL PostgreSQL o path SQLite
            database_url = os.getenv('DATABASE_URL')

            if database_url and database_url.startswith(('postgres://', 'postgresql://')):
                # PostgreSQL mode
                self.conn, self.db_type = get_database_connection(database_url)
                self.db_path = database_url
                logger.info("Database connesso: PostgreSQL (cloud)")
            else:
                # SQLite mode (locale)
                self.db_path = db_path or "data/ga4_data.db"
                self.conn, self.db_type = get_database_connection(f"sqlite:///{self.db_path}")
                logger.info(f"Database connesso: SQLite ({self.db_path})")

        self._placeholder = '%s' if self.db_type == 'postgresql' else '?'

        # Esegui migrations pendenti all'avvio
        if run_migrations:
            self._run_migrations()

    def _run_migrations(self):
        """
        Esegue migrations pendenti sul database.

        Viene chiamato automaticamente all'inizializzazione se run_migrations=True.
        """
        try:
            from backend.migrations import MigrationRunner
            runner = MigrationRunner(self.conn, self.db_type)

            status = runner.get_status()
            if status['pending_count'] > 0:
                logger.info(f"Trovate {status['pending_count']} migrations pendenti")
                applied, failed, messages = runner.run_all_pending()

                if failed > 0:
                    logger.error(f"Migrations fallite: {failed}")
                    for msg in messages:
                        logger.error(f"  {msg}")
                else:
                    logger.info(f"Migrations applicate con successo: {applied}")
            else:
                logger.debug("Nessuna migration pendente")

        except ImportError as e:
            # Se il modulo migrations non è disponibile, usa fallback a create_schema
            logger.warning(f"Modulo migrations non disponibile ({e}), uso create_schema come fallback")
            self.create_schema()
        except Exception as e:
            logger.error(f"Errore durante migrations: {e}")
            # Fallback a create_schema per garantire che le tabelle esistano
            logger.info("Fallback a create_schema")
            self.create_schema()

    def _ph(self, count: int = 1) -> str:
        """Genera placeholder per query parametrizzate."""
        return ', '.join([self._placeholder] * count)
    
    def _dict_row(self, row) -> Optional[Dict]:
        """Converte riga in dictionary (compatibile SQLite/PostgreSQL)."""
        if row is None:
            return None
        if self.db_type == 'postgresql':
            return dict(row)
        return dict(row)
    
    def _execute(self, query: str, params: tuple = ()) -> Any:
        """Esegue query con gestione cursor cross-database."""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor
    
    def create_schema(self):
        """Crea schema database con tabelle e indici."""
        cursor = self.conn.cursor()
        
        if self.db_type == 'postgresql':
            # PostgreSQL schema
            cursor.execute("""
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
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_date 
                ON daily_metrics(date DESC)
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products_performance (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    product_name TEXT NOT NULL,
                    total_conversions REAL NOT NULL,
                    percentage REAL NOT NULL,
                    UNIQUE(date, product_name)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_product_date 
                ON products_performance(date DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_product_name 
                ON products_performance(product_name)
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions_by_channel (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    channel TEXT NOT NULL,
                    commodity_sessions INTEGER NOT NULL,
                    lucegas_sessions INTEGER NOT NULL,
                    UNIQUE(date, channel)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_channel_date 
                ON sessions_by_channel(date DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_channel_name 
                ON sessions_by_channel(channel)
            """)
            
            # Tabella sessioni per campagna
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions_by_campaign (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    campaign TEXT NOT NULL,
                    commodity_sessions INTEGER NOT NULL,
                    lucegas_sessions INTEGER NOT NULL,
                    UNIQUE(date, campaign)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_campaign_date
                ON sessions_by_campaign(date DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_campaign_name
                ON sessions_by_campaign(campaign)
            """)

            # Tabella SWI per commodity type
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS swi_by_commodity (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    commodity_type TEXT NOT NULL,
                    conversions INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, commodity_type)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_swi_commodity_date
                ON swi_by_commodity(date DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_swi_commodity_type
                ON swi_by_commodity(commodity_type)
            """)

        else:
            # SQLite schema (originale)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    date DATE PRIMARY KEY,
                    extraction_timestamp DATETIME NOT NULL,
                    sessioni_commodity INTEGER NOT NULL,
                    sessioni_lucegas INTEGER NOT NULL,
                    swi_conversioni INTEGER NOT NULL,
                    cr_commodity REAL NOT NULL,
                    cr_lucegas REAL NOT NULL,
                    cr_canalizzazione REAL NOT NULL,
                    start_funnel INTEGER NOT NULL
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_date 
                ON daily_metrics(date DESC)
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    product_name TEXT NOT NULL,
                    total_conversions REAL NOT NULL,
                    percentage REAL NOT NULL,
                    FOREIGN KEY (date) REFERENCES daily_metrics(date) ON DELETE CASCADE,
                    UNIQUE(date, product_name)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_product_date 
                ON products_performance(date DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_product_name 
                ON products_performance(product_name)
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions_by_channel (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    channel TEXT NOT NULL,
                    commodity_sessions INTEGER NOT NULL,
                    lucegas_sessions INTEGER NOT NULL,
                    FOREIGN KEY (date) REFERENCES daily_metrics(date) ON DELETE CASCADE,
                    UNIQUE(date, channel)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_channel_date 
                ON sessions_by_channel(date DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_channel_name 
                ON sessions_by_channel(channel)
            """)
            
            # Tabella sessioni per campagna
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions_by_campaign (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    campaign TEXT NOT NULL,
                    commodity_sessions INTEGER NOT NULL,
                    lucegas_sessions INTEGER NOT NULL,
                    FOREIGN KEY (date) REFERENCES daily_metrics(date) ON DELETE CASCADE,
                    UNIQUE(date, campaign)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_campaign_date
                ON sessions_by_campaign(date DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_campaign_name
                ON sessions_by_campaign(campaign)
            """)

            # Tabella SWI per commodity type
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS swi_by_commodity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    commodity_type TEXT NOT NULL,
                    conversions INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (date) REFERENCES daily_metrics(date) ON DELETE CASCADE,
                    UNIQUE(date, commodity_type)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_swi_commodity_date
                ON swi_by_commodity(date DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_swi_commodity_type
                ON swi_by_commodity(commodity_type)
            """)

        self.conn.commit()
        logger.info(f"Schema database creato con successo ({self.db_type})")
    
    def insert_daily_metrics(
        self, 
        date: str, 
        metrics: Dict[str, Any],
        replace: bool = True
    ) -> bool:
        """
        Inserisce o aggiorna metriche giornaliere.
        
        Args:
            date: Data in formato YYYY-MM-DD
            metrics: Dictionary con metriche raw
            replace: Se True, sostituisce record esistente (default: True)
        
        Returns:
            True se successo, False altrimenti
        """
        try:
            cursor = self.conn.cursor()
            
            values = (
                date,
                datetime.now().isoformat(),
                metrics['sessioni_commodity'],
                metrics['sessioni_lucegas'],
                metrics['swi_conversioni'],
                metrics['cr_commodity'],
                metrics['cr_lucegas'],
                metrics['cr_canalizzazione'],
                metrics['start_funnel']
            )
            
            if self.db_type == 'postgresql':
                if replace:
                    cursor.execute("""
                        INSERT INTO daily_metrics 
                        (date, extraction_timestamp, sessioni_commodity, sessioni_lucegas,
                         swi_conversioni, cr_commodity, cr_lucegas, cr_canalizzazione, start_funnel)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (date) DO UPDATE SET
                            extraction_timestamp = EXCLUDED.extraction_timestamp,
                            sessioni_commodity = EXCLUDED.sessioni_commodity,
                            sessioni_lucegas = EXCLUDED.sessioni_lucegas,
                            swi_conversioni = EXCLUDED.swi_conversioni,
                            cr_commodity = EXCLUDED.cr_commodity,
                            cr_lucegas = EXCLUDED.cr_lucegas,
                            cr_canalizzazione = EXCLUDED.cr_canalizzazione,
                            start_funnel = EXCLUDED.start_funnel
                    """, values)
                else:
                    cursor.execute("""
                        INSERT INTO daily_metrics 
                        (date, extraction_timestamp, sessioni_commodity, sessioni_lucegas,
                         swi_conversioni, cr_commodity, cr_lucegas, cr_canalizzazione, start_funnel)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, values)
            else:
                # SQLite
                if replace:
                    cursor.execute("""
                        INSERT OR REPLACE INTO daily_metrics 
                        (date, extraction_timestamp, sessioni_commodity, sessioni_lucegas,
                         swi_conversioni, cr_commodity, cr_lucegas, cr_canalizzazione, start_funnel)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, values)
                else:
                    cursor.execute("""
                        INSERT INTO daily_metrics 
                        (date, extraction_timestamp, sessioni_commodity, sessioni_lucegas,
                         swi_conversioni, cr_commodity, cr_lucegas, cr_canalizzazione, start_funnel)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, values)
            
            self.conn.commit()
            logger.info(f"Metriche salvate per data: {date}")
            return True
            
        except Exception as e:
            # Log dettagliato per debug (es. vincoli o problemi di connessione)
            logger.error(f"Errore inserimento metriche per {date}: {e}", exc_info=True)
            self.conn.rollback()
            # Propaga per rendere visibile l'errore a livello API
            raise
    
    def insert_products(
        self, 
        date: str, 
        products: List[Dict[str, Any]],
        replace: bool = True
    ) -> bool:
        """
        Inserisce performance prodotti per una data.
        
        Args:
            date: Data in formato YYYY-MM-DD
            products: Lista di dict con product_name, total_conversions, percentage
            replace: Se True, elimina prodotti esistenti per quella data
        
        Returns:
            True se successo, False altrimenti
        """
        try:
            cursor = self.conn.cursor()
            ph = self._placeholder
            
            # Se replace, elimina prodotti esistenti per questa data
            if replace:
                cursor.execute(
                    f"DELETE FROM products_performance WHERE date = {ph}",
                    (date,)
                )
            
            # Inserisci nuovi prodotti
            for product in products:
                if self.db_type == 'postgresql':
                    cursor.execute("""
                        INSERT INTO products_performance 
                        (date, product_name, total_conversions, percentage)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        date,
                        product['product_name'],
                        product['total_conversions'],
                        product['percentage']
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO products_performance 
                        (date, product_name, total_conversions, percentage)
                        VALUES (?, ?, ?, ?)
                    """, (
                        date,
                        product['product_name'],
                        product['total_conversions'],
                        product['percentage']
                    ))
            
            self.conn.commit()
            logger.info(f"Prodotti salvati per data {date}: {len(products)} prodotti")
            return True
            
        except Exception as e:
            logger.error(f"Errore inserimento prodotti per {date}: {e}", exc_info=True)
            self.conn.rollback()
            raise
    
    def insert_sessions_by_channel(
        self, 
        date: str, 
        channels: List[Dict[str, Any]],
        replace: bool = True
    ) -> bool:
        """
        Inserisce sessioni per canale per una data.
        
        Args:
            date: Data in formato YYYY-MM-DD
            channels: Lista di dict con channel, commodity_sessions, lucegas_sessions
            replace: Se True, elimina sessioni esistenti per quella data
        
        Returns:
            True se successo, False altrimenti
        """
        try:
            cursor = self.conn.cursor()
            ph = self._placeholder
            
            # Se replace, elimina sessioni esistenti per questa data
            if replace:
                cursor.execute(
                    f"DELETE FROM sessions_by_channel WHERE date = {ph}",
                    (date,)
                )
            
            # Inserisci nuovi canali
            for channel in channels:
                if self.db_type == 'postgresql':
                    cursor.execute("""
                        INSERT INTO sessions_by_channel 
                        (date, channel, commodity_sessions, lucegas_sessions)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        date,
                        channel['channel'],
                        channel['commodity_sessions'],
                        channel['lucegas_sessions']
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO sessions_by_channel 
                        (date, channel, commodity_sessions, lucegas_sessions)
                        VALUES (?, ?, ?, ?)
                    """, (
                        date,
                        channel['channel'],
                        channel['commodity_sessions'],
                        channel['lucegas_sessions']
                    ))
            
            self.conn.commit()
            logger.info(f"Sessioni per canale salvate per data {date}: {len(channels)} canali")
            return True
            
        except Exception as e:
            logger.error(f"Errore inserimento sessioni per canale per {date}: {e}")
            self.conn.rollback()
            return False
    
    def get_sessions_by_channel(self, date: str) -> List[Dict[str, Any]]:
        """
        Recupera sessioni per canale per una data.
        
        Args:
            date: Data in formato YYYY-MM-DD
        
        Returns:
            Lista di dict con sessioni per canale ordinate per commodity_sessions DESC
        """
        cursor = self.conn.cursor()
        ph = self._placeholder
        cursor.execute(f"""
            SELECT * FROM sessions_by_channel 
            WHERE date = {ph}
            ORDER BY commodity_sessions DESC
        """, (date,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def insert_sessions_by_campaign(
        self, 
        date: str, 
        campaigns: List[Dict[str, Any]],
        replace: bool = True
    ) -> bool:
        """
        Inserisce sessioni per campagna per una data.
        
        Args:
            date: Data in formato YYYY-MM-DD
            campaigns: Lista di dict con campaign, commodity_sessions, lucegas_sessions
            replace: Se True, elimina sessioni esistenti per quella data
        
        Returns:
            True se successo, False altrimenti
        """
        try:
            cursor = self.conn.cursor()
            ph = self._placeholder
            
            # Se replace, elimina sessioni esistenti per questa data
            if replace:
                cursor.execute(
                    f"DELETE FROM sessions_by_campaign WHERE date = {ph}",
                    (date,)
                )
            
            # Inserisci nuove campagne
            for campaign in campaigns:
                if self.db_type == 'postgresql':
                    cursor.execute("""
                        INSERT INTO sessions_by_campaign 
                        (date, campaign, commodity_sessions, lucegas_sessions)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        date,
                        campaign['campaign'],
                        campaign['commodity_sessions'],
                        campaign['lucegas_sessions']
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO sessions_by_campaign 
                        (date, campaign, commodity_sessions, lucegas_sessions)
                        VALUES (?, ?, ?, ?)
                    """, (
                        date,
                        campaign['campaign'],
                        campaign['commodity_sessions'],
                        campaign['lucegas_sessions']
                    ))
            
            self.conn.commit()
            logger.info(f"Sessioni per campagna salvate per data {date}: {len(campaigns)} campagne")
            return True
            
        except Exception as e:
            logger.error(f"Errore inserimento sessioni per campagna per {date}: {e}")
            self.conn.rollback()
            return False
    
    def get_sessions_by_campaign(self, date: str) -> List[Dict[str, Any]]:
        """
        Recupera sessioni per campagna per una data.
        
        Args:
            date: Data in formato YYYY-MM-DD
        
        Returns:
            Lista di dict con sessioni per campagna ordinate per commodity_sessions DESC
        """
        cursor = self.conn.cursor()
        ph = self._placeholder
        cursor.execute(f"""
            SELECT * FROM sessions_by_campaign 
            WHERE date = {ph}
            ORDER BY commodity_sessions DESC
        """, (date,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def insert_swi_by_commodity(
        self,
        date: str,
        commodities: List[Dict[str, Any]],
        replace: bool = True
    ) -> bool:
        """
        Inserisce conversioni SWI per tipo commodity per una data.

        Args:
            date: Data in formato YYYY-MM-DD
            commodities: Lista di dict con commodity_type, conversions
            replace: Se True, elimina record esistenti per quella data

        Returns:
            True se successo, False altrimenti
        """
        try:
            cursor = self.conn.cursor()
            ph = self._placeholder

            if replace:
                cursor.execute(
                    f"DELETE FROM swi_by_commodity WHERE date = {ph}",
                    (date,)
                )

            for commodity in commodities:
                if self.db_type == 'postgresql':
                    cursor.execute("""
                        INSERT INTO swi_by_commodity
                        (date, commodity_type, conversions)
                        VALUES (%s, %s, %s)
                    """, (
                        date,
                        commodity['commodity_type'],
                        commodity['conversions']
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO swi_by_commodity
                        (date, commodity_type, conversions)
                        VALUES (?, ?, ?)
                    """, (
                        date,
                        commodity['commodity_type'],
                        commodity['conversions']
                    ))

            self.conn.commit()
            logger.info(f"SWI per commodity salvati per data {date}: {len(commodities)} tipi")
            return True

        except Exception as e:
            logger.error(f"Errore inserimento SWI per commodity per {date}: {e}")
            self.conn.rollback()
            return False

    def get_swi_by_commodity(self, date: str) -> List[Dict[str, Any]]:
        """
        Recupera conversioni SWI per tipo commodity per una data.

        Args:
            date: Data in formato YYYY-MM-DD

        Returns:
            Lista di dict con conversioni per commodity type ordinate per conversions DESC
        """
        cursor = self.conn.cursor()
        ph = self._placeholder
        cursor.execute(f"""
            SELECT * FROM swi_by_commodity
            WHERE date = {ph}
            ORDER BY conversions DESC
        """, (date,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_metrics(self, date: str) -> Optional[Dict[str, Any]]:
        """
        Recupera metriche per una data specifica.
        
        Args:
            date: Data in formato YYYY-MM-DD
        
        Returns:
            Dictionary con metriche o None se non trovate
        """
        cursor = self.conn.cursor()
        ph = self._placeholder
        cursor.execute(
            f"SELECT * FROM daily_metrics WHERE date = {ph}",
            (date,)
        )
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
            # Normalizza il campo date come stringa
            if 'date' in result and hasattr(result['date'], 'isoformat'):
                result['date'] = result['date'].isoformat()
            return result
        return None
    
    def get_products(self, date: str) -> List[Dict[str, Any]]:
        """
        Recupera performance prodotti per una data.
        
        Args:
            date: Data in formato YYYY-MM-DD
        
        Returns:
            Lista di dict con prodotti
        """
        cursor = self.conn.cursor()
        ph = self._placeholder
        cursor.execute(
            f"SELECT * FROM products_performance WHERE date = {ph} ORDER BY total_conversions DESC",
            (date,)
        )
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def get_date_range(
        self, 
        start_date: str, 
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        Recupera metriche per un range di date.
        
        Args:
            start_date: Data inizio (YYYY-MM-DD)
            end_date: Data fine (YYYY-MM-DD)
        
        Returns:
            Lista di dict con metriche ordinate per data
        """
        cursor = self.conn.cursor()
        ph = self._placeholder
        cursor.execute(f"""
            SELECT * FROM daily_metrics 
            WHERE date BETWEEN {ph} AND {ph}
            ORDER BY date ASC
        """, (start_date, end_date))
        
        rows = cursor.fetchall()
        result = []
        for row in rows:
            r = dict(row)
            # Normalizza il campo date come stringa
            if 'date' in r and hasattr(r['date'], 'isoformat'):
                r['date'] = r['date'].isoformat()
            result.append(r)
        return result
    
    def calculate_comparison(
        self, 
        current_date: str, 
        days_ago: int = 7
    ) -> Optional[Dict[str, Any]]:
        """
        Calcola confronto dinamico tra data corrente e N giorni prima.
        
        Args:
            current_date: Data corrente (YYYY-MM-DD)
            days_ago: Giorni indietro per confronto (default: 7)
        
        Returns:
            Dict con current, previous e change% per tutte le metriche
        """
        # Recupera metriche correnti
        current = self.get_metrics(current_date)
        if not current:
            logger.warning(f"Metriche non trovate per data: {current_date}")
            return None
        
        # Calcola data precedente
        date_obj = datetime.strptime(current_date, '%Y-%m-%d')
        previous_date_obj = date_obj - timedelta(days=days_ago)
        previous_date = previous_date_obj.strftime('%Y-%m-%d')
        
        # Recupera metriche precedenti
        previous = self.get_metrics(previous_date)
        if not previous:
            logger.warning(f"Metriche non trovate per data confronto: {previous_date}")
            return {
                'current': current,
                'previous': None,
                'comparison': None
            }
        
        # Calcola change% per ogni metrica
        def calc_change(current_val, previous_val):
            if previous_val == 0:
                return 0.0
            return ((current_val - previous_val) / previous_val) * 100
        
        comparison = {
            'sessioni_commodity_change': calc_change(
                current['sessioni_commodity'], 
                previous['sessioni_commodity']
            ),
            'sessioni_lucegas_change': calc_change(
                current['sessioni_lucegas'], 
                previous['sessioni_lucegas']
            ),
            'swi_conversioni_change': calc_change(
                current['swi_conversioni'], 
                previous['swi_conversioni']
            ),
            'cr_commodity_change': calc_change(
                current['cr_commodity'], 
                previous['cr_commodity']
            ),
            'cr_lucegas_change': calc_change(
                current['cr_lucegas'], 
                previous['cr_lucegas']
            ),
        }
        
        return {
            'current': current,
            'previous': previous,
            'comparison': comparison,
            'current_date': current_date,
            'previous_date': previous_date,
            'days_offset': days_ago
        }
    
    def get_latest_date(self) -> Optional[str]:
        """
        Recupera la data più recente disponibile nel database.
        
        Returns:
            Data in formato YYYY-MM-DD o None se DB vuoto
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT date FROM daily_metrics ORDER BY date DESC LIMIT 1"
        )
        row = cursor.fetchone()
        
        if row:
            date_val = row['date'] if isinstance(row, dict) else row[0]
            # Normalizza come stringa
            if hasattr(date_val, 'isoformat'):
                return date_val.isoformat()
            return str(date_val)
        return None
    
    def get_record_count(self) -> int:
        """
        Conta il numero di record nel database.
        
        Returns:
            Numero di giorni di dati disponibili
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM daily_metrics")
        row = cursor.fetchone()
        if row:
            return row['count'] if isinstance(row, dict) else row[0]
        return 0
    
    def get_date_exists(self, date: str) -> bool:
        """
        Verifica se esistono dati per una data specifica.
        
        Args:
            date: Data in formato YYYY-MM-DD
        
        Returns:
            True se dati presenti, False altrimenti
        """
        return self.get_metrics(date) is not None
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Recupera statistiche generali sul database.
        
        Returns:
            Dict con statistiche (min_date, max_date, record_count, etc.)
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                MIN(date) as min_date,
                MAX(date) as max_date,
                COUNT(*) as record_count,
                AVG(sessioni_commodity) as avg_sessioni_commodity,
                AVG(swi_conversioni) as avg_swi_conversioni
            FROM daily_metrics
        """)
        
        row = cursor.fetchone()
        
        if row:
            result = dict(row) if isinstance(row, dict) else {
                'min_date': row[0],
                'max_date': row[1],
                'record_count': row[2],
                'avg_sessioni_commodity': row[3],
                'avg_swi_conversioni': row[4]
            }
            if result.get('record_count', 0) > 0:
                # Normalizza date come stringhe
                for key in ['min_date', 'max_date']:
                    if key in result and result[key] and hasattr(result[key], 'isoformat'):
                        result[key] = result[key].isoformat()
                return result
        
        return {
            'min_date': None,
            'max_date': None,
            'record_count': 0,
            'avg_sessioni_commodity': 0,
            'avg_swi_conversioni': 0
        }
    
    def data_exists(self, date: str, check_products: bool = False) -> bool:
        """
        Verifica se esistono dati completi per una data specifica.
        
        Args:
            date: Data in formato YYYY-MM-DD
            check_products: Se True, verifica anche presenza prodotti (default: False)
        
        Returns:
            True se dati esistono e sono completi, False altrimenti
        """
        try:
            # Check metriche principali
            metrics = self.get_metrics(date)
            if not metrics:
                return False
            
            # Verifica che i campi essenziali non siano nulli/zero
            essential_fields = ['sessioni_commodity', 'swi_conversioni']
            for field in essential_fields:
                if metrics.get(field) is None or metrics.get(field) == 0:
                    logger.debug(f"Campo {field} mancante o zero per {date}")
                    return False
            
            # Check prodotti se richiesto
            if check_products:
                products = self.get_products(date)
                if not products or len(products) == 0:
                    logger.debug(f"Prodotti mancanti per {date}")
                    return False
            
            return True

        except Exception as e:
            logger.error(f"Errore verifica esistenza dati per {date}: {e}")
            return False

    def get_table_dates(self, table_name: str) -> set:
        """
        Recupera tutte le date uniche presenti in una tabella.

        Args:
            table_name: Nome della tabella (daily_metrics, products_performance, etc.)

        Returns:
            Set di date in formato stringa YYYY-MM-DD
        """
        valid_tables = [
            'daily_metrics', 'products_performance', 'swi_by_commodity',
            'sessions_by_channel', 'sessions_by_campaign'
        ]

        if table_name not in valid_tables:
            logger.warning(f"Tabella non valida: {table_name}")
            return set()

        try:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT DISTINCT date FROM {table_name} ORDER BY date")
            rows = cursor.fetchall()

            dates = set()
            for row in rows:
                date_val = row['date'] if isinstance(row, dict) else row[0]
                if hasattr(date_val, 'isoformat'):
                    dates.add(date_val.isoformat())
                else:
                    dates.add(str(date_val))

            return dates

        except Exception as e:
            logger.error(f"Errore recupero date da {table_name}: {e}")
            return set()

    def check_alignment_status(self) -> dict:
        """
        Verifica lo stato di allineamento di tutte le tabelle rispetto a daily_metrics.

        Regole:
        - products_performance: stesse date di daily_metrics
        - swi_by_commodity: stesse date di daily_metrics
        - sessions_by_channel: date fino a max_date - 2 giorni (D-2)
        - sessions_by_campaign: date fino a max_date - 2 giorni (D-2)

        Returns:
            Dict con status di allineamento per ogni tabella
        """
        from datetime import datetime, timedelta

        # Configurazione tabelle satellite
        table_config = {
            'products_performance': {'delay_days': 0},
            'swi_by_commodity': {'delay_days': 0},
            'sessions_by_channel': {'delay_days': 2},
            'sessions_by_campaign': {'delay_days': 2},
        }

        # Recupera date di riferimento da daily_metrics
        reference_dates = self.get_table_dates('daily_metrics')

        if not reference_dates:
            return {
                'reference': {
                    'table': 'daily_metrics',
                    'count': 0,
                    'min_date': None,
                    'max_date': None
                },
                'tables': {},
                'summary': {
                    'all_aligned': True,
                    'tables_missing_data': []
                }
            }

        sorted_dates = sorted(reference_dates)
        min_date = sorted_dates[0]
        max_date = sorted_dates[-1]
        max_date_obj = datetime.strptime(max_date, '%Y-%m-%d')

        result = {
            'reference': {
                'table': 'daily_metrics',
                'count': len(reference_dates),
                'min_date': min_date,
                'max_date': max_date,
                'dates': reference_dates
            },
            'tables': {},
            'summary': {
                'all_aligned': True,
                'tables_missing_data': []
            }
        }

        # Verifica ogni tabella satellite
        for table_name, config in table_config.items():
            delay_days = config['delay_days']

            # Calcola date attese
            if delay_days > 0:
                cutoff_date = (max_date_obj - timedelta(days=delay_days)).strftime('%Y-%m-%d')
                expected_dates = {d for d in reference_dates if d <= cutoff_date}
            else:
                expected_dates = reference_dates.copy()

            # Recupera date esistenti
            actual_dates = self.get_table_dates(table_name)

            # Calcola date mancanti
            missing_dates = sorted(expected_dates - actual_dates)

            is_aligned = len(missing_dates) == 0

            result['tables'][table_name] = {
                'delay_days': delay_days,
                'expected_count': len(expected_dates),
                'actual_count': len(actual_dates),
                'missing_count': len(missing_dates),
                'missing_dates': missing_dates,
                'aligned': is_aligned
            }

            if not is_aligned:
                result['summary']['all_aligned'] = False
                result['summary']['tables_missing_data'].append(table_name)

        return result

    def close(self):
        """
        Chiude connessione database.
        
        Se la connessione proviene da un pool (owns_connection=False),
        NON viene chiusa qui ma ritornata al pool dal chiamante.
        """
        if self.conn and self._owns_connection:
            self.conn.close()
            logger.info("Connessione database chiusa")
        elif self.conn and not self._owns_connection:
            logger.debug("Pooled connection not closed (managed by pool)")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


if __name__ == "__main__":
    # Test del modulo
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("Testing GA4Database...")
    
    # Test connessione
    db = GA4Database("data/test_ga4.db")
    db.create_schema()
    
    # Test inserimento
    test_date = "2025-11-01"
    test_metrics = {
        'sessioni_commodity': 150,
        'sessioni_lucegas': 25000,
        'swi_conversioni': 200,
        'cr_commodity': 133.33,
        'cr_lucegas': 0.80,
        'cr_canalizzazione': 35.5,
        'start_funnel': 563
    }
    
    success = db.insert_daily_metrics(test_date, test_metrics)
    print(f"✓ Inserimento metriche: {'OK' if success else 'FAILED'}")
    
    # Test recupero
    metrics = db.get_metrics(test_date)
    print(f"✓ Recupero metriche: {metrics is not None}")
    
    # Test statistiche
    stats = db.get_statistics()
    print(f"✓ Statistiche: {stats['record_count']} record")
    
    db.close()
    print("✓ Test completato")
