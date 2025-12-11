"""
Database Connection Pool per API Flask.

Gestisce un pool di connessioni database per ridurre overhead
e migliorare performance.
"""

import os
import logging
from contextlib import contextmanager
from threading import Lock

logger = logging.getLogger(__name__)


class DatabasePool:
    """
    Connection pool per database.
    
    Supporta sia SQLite (thread-safe) che PostgreSQL (con psycopg2.pool).
    """
    
    def __init__(self, db_path: str = None, pool_size: int = 10):
        """
        Inizializza connection pool.
        
        Args:
            db_path: Path database SQLite o DATABASE_URL per PostgreSQL
            pool_size: Dimensione pool (solo per PostgreSQL)
        """
        self.db_path = db_path or os.getenv('DATABASE_URL') or 'data/ga4_data.db'
        self.pool_size = pool_size
        self.pool = None
        self._lock = Lock()
        
        # Determina tipo database
        if self.db_path.startswith(('postgres://', 'postgresql://')):
            self.db_type = 'postgresql'
            self._init_postgres_pool()
        else:
            self.db_type = 'sqlite'
            self._init_sqlite_pool()
        
        logger.info(f"Database pool initialized: {self.db_type}, size={pool_size}")
    
    def _init_postgres_pool(self):
        """Inizializza pool PostgreSQL con psycopg2."""
        try:
            import psycopg2.pool
            
            # Fix URL per psycopg2 (postgres:// → postgresql://)
            url = self.db_path
            if url.startswith('postgres://'):
                url = url.replace('postgres://', 'postgresql://', 1)
            
            # Forza SSL se non specificato
            if 'sslmode=' not in url:
                separator = '&' if '?' in url else '?'
                url = f"{url}{separator}sslmode=require"
            
            # Crea connection pool
            self.pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=self.pool_size,
                dsn=url
            )
            
            logger.info("PostgreSQL connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL pool: {e}")
            raise
    
    def _init_sqlite_pool(self):
        """
        Inizializza pool SQLite (semplificato).
        
        SQLite non ha vero pooling (file-based), ma usa connessioni thread-safe.
        """
        import sqlite3
        from pathlib import Path
        
        # Crea directory se non esiste
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # Test connessione
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.close()
            logger.info(f"SQLite database ready: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Context manager per ottenere connessione dal pool.
        
        Usage:
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM table")
        
        Yields:
            Database connection
        """
        conn = None
        try:
            if self.db_type == 'postgresql':
                # Ottieni connessione dal pool
                with self._lock:
                    conn = self.pool.getconn()
                yield conn
            else:
                # SQLite: crea nuova connessione (thread-safe)
                import sqlite3
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            if conn and self.db_type == 'postgresql':
                # Rollback in caso di errore
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            if conn:
                if self.db_type == 'postgresql':
                    # Ritorna connessione al pool
                    with self._lock:
                        self.pool.putconn(conn)
                else:
                    # Chiudi connessione SQLite
                    conn.close()
    
    def close(self):
        """Chiude pool e rilascia risorse."""
        if self.pool and self.db_type == 'postgresql':
            self.pool.closeall()
            logger.info("PostgreSQL connection pool closed")


# =============================================================================
# GLOBAL POOL INSTANCE
# =============================================================================

_pool = None
_pool_lock = Lock()


def get_pool(db_path: str = None, pool_size: int = 10) -> DatabasePool:
    """
    Ottiene pool singleton.
    
    Args:
        db_path: Path database (opzionale)
        pool_size: Dimensione pool (default: 10)
    
    Returns:
        DatabasePool instance
    """
    global _pool
    
    if _pool is None:
        with _pool_lock:
            if _pool is None:  # Double-check locking
                _pool = DatabasePool(db_path, pool_size)
    
    return _pool


def close_pool():
    """Chiude pool globale."""
    global _pool
    
    if _pool:
        with _pool_lock:
            if _pool:
                _pool.close()
                _pool = None
