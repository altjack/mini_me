#!/usr/bin/env python3
"""
SQLite Database Manager per dati GA4.

Gestisce lo storage permanente delle metriche GA4 con schema normalizzato.
Ogni giorno viene salvato come record unico senza duplicazioni.
"""

import sqlite3
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class GA4Database:
    """Manager per database SQLite delle metriche GA4."""
    
    def __init__(self, db_path: str = "data/ga4_data.db"):
        """
        Inizializza connessione al database.
        
        Args:
            db_path: Percorso file database SQLite
        """
        self.db_path = db_path
        
        # Crea directory se non esiste
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # Connessione con row_factory per dict-like access
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        logger.info(f"Database connesso: {db_path}")
    
    def create_schema(self):
        """Crea schema database con tabelle e indici."""
        cursor = self.conn.cursor()
        
        # Tabella daily_metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_metrics (
                date DATE PRIMARY KEY,
                extraction_timestamp DATETIME NOT NULL,
                
                -- Sessioni (valori assoluti del giorno)
                sessioni_commodity INTEGER NOT NULL,
                sessioni_lucegas INTEGER NOT NULL,
                
                -- Conversioni
                swi_conversioni INTEGER NOT NULL,
                
                -- Conversion Rates (percentuali)
                cr_commodity REAL NOT NULL,
                cr_lucegas REAL NOT NULL,
                cr_canalizzazione REAL NOT NULL,
                
                -- Funnel
                start_funnel INTEGER NOT NULL
            )
        """)
        
        # Indice per query ordinate per data
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_date 
            ON daily_metrics(date DESC)
        """)
        
        # Tabella products_performance
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
        
        # Indici per products
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_date 
            ON products_performance(date DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_name 
            ON products_performance(product_name)
        """)
        
        # Tabella sessions_by_channel
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
        
        # Indici per sessions_by_channel
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_channel_date 
            ON sessions_by_channel(date DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_channel_name 
            ON sessions_by_channel(channel)
        """)
        
        self.conn.commit()
        logger.info("Schema database creato con successo")
    
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
            
            # Prepara valori
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
            
        except sqlite3.Error as e:
            logger.error(f"Errore inserimento metriche per {date}: {e}")
            self.conn.rollback()
            return False
    
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
            
            # Se replace, elimina prodotti esistenti per questa data
            if replace:
                cursor.execute(
                    "DELETE FROM products_performance WHERE date = ?",
                    (date,)
                )
            
            # Inserisci nuovi prodotti
            for product in products:
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
            
        except sqlite3.Error as e:
            logger.error(f"Errore inserimento prodotti per {date}: {e}")
            self.conn.rollback()
            return False
    
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
            
            # Se replace, elimina sessioni esistenti per questa data
            if replace:
                cursor.execute(
                    "DELETE FROM sessions_by_channel WHERE date = ?",
                    (date,)
                )
            
            # Inserisci nuovi canali
            for channel in channels:
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
            
        except sqlite3.Error as e:
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
        cursor.execute("""
            SELECT * FROM sessions_by_channel 
            WHERE date = ? 
            ORDER BY commodity_sessions DESC
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
        cursor.execute(
            "SELECT * FROM daily_metrics WHERE date = ?",
            (date,)
        )
        row = cursor.fetchone()
        
        if row:
            return dict(row)
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
        cursor.execute(
            "SELECT * FROM products_performance WHERE date = ? ORDER BY total_conversions DESC",
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
        cursor.execute("""
            SELECT * FROM daily_metrics 
            WHERE date BETWEEN ? AND ?
            ORDER BY date ASC
        """, (start_date, end_date))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
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
            return row['date']
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
        return row['count'] if row else 0
    
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
        
        if row and row['record_count'] > 0:
            return dict(row)
        
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
    
    def close(self):
        """Chiude connessione database."""
        if self.conn:
            self.conn.close()
            logger.info("Connessione database chiusa")
    
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

