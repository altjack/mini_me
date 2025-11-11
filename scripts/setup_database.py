#!/usr/bin/env python3
"""
Script di setup per database GA4.

Inizializza schema SQLite e verifica connessione Redis.
Esegui questo script prima del backfill.
"""

import sys
import os
import logging
from pathlib import Path

# Aggiungi directory parent al path (per import da ga4_extraction)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ga4_extraction.database import GA4Database
from ga4_extraction.redis_cache import GA4RedisCache

# Setup logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'setup_database.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Setup iniziale database e cache."""
    
    print("=" * 80)
    print("  🚀 SETUP DATABASE GA4")
    print("=" * 80)
    print()
    
    # ========== STEP 1: Crea directory ==========
    print("[1/4] Creazione directory...")
    
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    print(f"  ✓ Directory creata: {data_dir.absolute()}")
    
    backups_dir = Path("data/backups")
    backups_dir.mkdir(exist_ok=True)
    print(f"  ✓ Directory backups creata: {backups_dir.absolute()}")
    print()
    
    # ========== STEP 2: Setup SQLite ==========
    print("[2/4] Inizializzazione database SQLite...")
    
    try:
        db_path = "data/ga4_data.db"
        db = GA4Database(db_path)
        
        print(f"  ✓ Database connesso: {Path(db_path).absolute()}")
        
        # Crea schema
        db.create_schema()
        print("  ✓ Schema creato con successo")
        
        # Verifica tabelle
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"  ✓ Tabelle create: {', '.join(tables)}")
        
        # Statistiche iniziali
        stats = db.get_statistics()
        print(f"  ✓ Record esistenti: {stats['record_count']}")
        
        db.close()
        print()
        
    except Exception as e:
        print(f"  ✗ Errore setup SQLite: {e}")
        logger.error(f"Errore setup SQLite: {e}", exc_info=True)
        return 1
    
    # ========== STEP 3: Test Redis ==========
    print("[3/4] Verifica connessione Redis...")
    
    try:
        cache = GA4RedisCache(
            host="localhost",
            port=6379,
            db=1,
            key_prefix="ga4:metrics:",
            ttl_days=14
        )
        
        # Test connessione
        if cache.test_connection():
            print("  ✓ Redis connesso: localhost:6379 (db=1)")
        else:
            raise Exception("Ping Redis fallito")
        
        # Info cache
        info = cache.get_cache_info()
        print(f"  ✓ TTL configurato: {info['ttl_days']} giorni")
        print(f"  ✓ Dati cached: {info['cached_days']} giorni")
        
        cache.close()
        print()
        
    except Exception as e:
        print(f"  ✗ Errore connessione Redis: {e}")
        print()
        print("  ⚠️  REDIS NON DISPONIBILE")
        print("     Redis è necessario per il funzionamento ottimale.")
        print()
        print("  📝 Per installare e avviare Redis:")
        print("     macOS:   brew install redis && redis-server &")
        print("     Linux:   sudo apt install redis-server && redis-server &")
        print()
        logger.warning(f"Redis non disponibile: {e}")
        # Non è un errore fatale, continua
    
    # ========== STEP 4: Riepilogo ==========
    print("[4/4] Riepilogo setup...")
    print()
    print("  ✅ Setup completato con successo!")
    print()
    print("  📊 PROSSIMI PASSI:")
    print()
    print("  1. Popola database con storico 60 giorni:")
    print("     python backfill_ga4.py")
    print()
    print("  2. Esegui estrazione giornaliera:")
    print("     python main.py")
    print()
    print("  3. Esegui agente per generare email:")
    print("     python run_agent.py")
    print()
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrotto dall'utente")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Errore imprevisto: {e}")
        logger.error(f"Errore imprevisto: {e}", exc_info=True)
        sys.exit(1)

