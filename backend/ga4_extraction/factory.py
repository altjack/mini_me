#!/usr/bin/env python3
"""
Factory per creazione risorse GA4 (Database e Redis Cache).

Implementa pattern Factory per centralizzare la creazione di istanze
con gestione configurazione e dependency injection.
"""

import logging
from typing import Tuple, Optional, Dict, Any
from pathlib import Path

from .database import GA4Database
from .redis_cache import GA4RedisCache

logger = logging.getLogger(__name__)


class GA4ResourceFactory:
    """
    Factory per creare istanze GA4Database e GA4RedisCache.
    
    Centralizza la logica di creazione risorse con:
    - Gestione configurazione unificata
    - Gestione errori Redis centralizzata
    - Dependency injection per testabilità
    """
    
    @staticmethod
    def create_from_config(config: Dict[str, Any]) -> Tuple[GA4Database, Optional[GA4RedisCache]]:
        """
        Crea istanze Database e Redis Cache da configurazione.
        
        Args:
            config: Dictionary configurazione (da config.yaml)
                   Deve contenere sezione 'database' con 'sqlite' e 'redis'
        
        Returns:
            Tuple (GA4Database, GA4RedisCache|None)
            Redis è None se non disponibile o configurazione mancante
        
        Example:
            config = {
                'database': {
                    'sqlite': {'path': 'data/ga4_data.db'},
                    'redis': {
                        'host': 'localhost',
                        'port': 6379,
                        'db': 1,
                        'key_prefix': 'ga4:metrics:',
                        'ttl_days': 14
                    }
                }
            }
            db, cache = GA4ResourceFactory.create_from_config(config)
        """
        # Estrai configurazione database
        db_config = config.get('database', {})
        
        # Crea Database (obbligatorio)
        db = GA4ResourceFactory._create_database(db_config)
        
        # Crea Redis Cache (opzionale)
        cache = GA4ResourceFactory._create_redis_cache(db_config)
        
        return db, cache
    
    @staticmethod
    def _create_database(db_config: Dict[str, Any]) -> GA4Database:
        """
        Crea istanza GA4Database.
        
        Args:
            db_config: Configurazione database
        
        Returns:
            Istanza GA4Database
        
        Raises:
            ValueError: Se configurazione mancante
        """
        sqlite_config = db_config.get('sqlite', {})
        db_path = sqlite_config.get('path', 'data/ga4_data.db')
        
        # Crea directory se non esiste
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Creazione database: {db_path}")
        db = GA4Database(db_path)
        
        # Assicura che lo schema esista
        db.create_schema()
        
        return db
    
    @staticmethod
    def _create_redis_cache(db_config: Dict[str, Any]) -> Optional[GA4RedisCache]:
        """
        Crea istanza GA4RedisCache con gestione errori.
        
        Args:
            db_config: Configurazione database (contiene sezione 'redis')
        
        Returns:
            Istanza GA4RedisCache o None se non disponibile
        
        Environment Variables (override config.yaml):
            REDIS_HOST: Host Redis (es. my-redis.upstash.io)
            REDIS_PORT: Porta Redis (default: 6379)
            REDIS_TOKEN: Token/Password Redis (per Upstash/Redis Cloud)
            REDIS_DB: Database number (default: 1)
            REDIS_SSL: Se "true", usa connessione SSL (richiesto da Upstash)
        """
        import os
        
        redis_config = db_config.get('redis', {})
        
        if not redis_config:
            logger.info("Configurazione Redis non trovata, cache disabilitata")
            return None
        
        # Priorità: env vars > config.yaml
        # Accetta sia REDIS_TOKEN (Upstash) che REDIS_PASSWORD (standard)
        redis_host = os.getenv('REDIS_HOST') or redis_config.get('host', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT') or redis_config.get('port', 6379))
        redis_password = os.getenv('REDIS_TOKEN') or os.getenv('REDIS_PASSWORD') or redis_config.get('password')
        redis_db = int(os.getenv('REDIS_DB') or redis_config.get('db', 1))
        redis_ssl = os.getenv('REDIS_SSL', '').lower() == 'true' or redis_config.get('ssl', False)
        
        try:
            cache = GA4RedisCache(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                ssl=redis_ssl,
                key_prefix=redis_config.get('key_prefix', 'ga4:metrics:'),
                ttl_days=redis_config.get('ttl_days', 14)
            )
            logger.info(f"✓ Redis cache connessa ({redis_host}:{redis_port})")
            return cache
            
        except Exception as e:
            logger.warning(f"Redis non disponibile: {e}")
            logger.info("Continuando senza cache Redis (solo SQLite)")
            return None
    
    @staticmethod
    def create_database_only(db_path: str = "data/ga4_data.db") -> GA4Database:
        """
        Crea solo istanza Database senza Redis.
        
        Utile per script che non necessitano cache.
        
        Args:
            db_path: Percorso file database
        
        Returns:
            Istanza GA4Database
        """
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        db = GA4Database(db_path)
        db.create_schema()
        
        return db


if __name__ == "__main__":
    # Test del factory
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("Testing GA4ResourceFactory...")
    
    # Test configurazione completa
    test_config = {
        'database': {
            'sqlite': {'path': 'data/test_factory.db'},
            'redis': {
                'host': 'localhost',
                'port': 6379,
                'db': 1,
                'key_prefix': 'test:',
                'ttl_days': 7
            }
        }
    }
    
    db, cache = GA4ResourceFactory.create_from_config(test_config)
    print(f"✓ Database creato: {db is not None}")
    print(f"✓ Redis cache: {'Disponibile' if cache else 'Non disponibile'}")
    
    # Cleanup
    if db:
        db.close()
    if cache:
        cache.close()
    
    print("✓ Test completato")

