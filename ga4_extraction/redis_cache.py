#!/usr/bin/env python3
"""
Redis Cache Manager per dati GA4.

Gestisce cache veloce delle metriche GA4 con TTL automatico di 14 giorni.
Sliding window: mantiene sempre gli ultimi 14 giorni in cache.
"""

import redis
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class GA4RedisCache:
    """Manager per cache Redis delle metriche GA4."""
    
    def __init__(
        self, 
        host: str = "localhost",
        port: int = 6379,
        db: int = 1,
        key_prefix: str = "ga4:metrics:",
        ttl_days: int = 14
    ):
        """
        Inizializza connessione Redis.
        
        Args:
            host: Host Redis (default: localhost)
            port: Porta Redis (default: 6379)
            db: Database Redis (default: 1, separato da memoria agente)
            key_prefix: Prefisso chiavi (default: ga4:metrics:)
            ttl_days: TTL in giorni (default: 14)
        """
        self.host = host
        self.port = port
        self.db = db
        self.key_prefix = key_prefix
        self.ttl_seconds = ttl_days * 24 * 60 * 60  # Converti giorni in secondi
        
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True  # Auto-decode bytes to strings
            )
            # Test connessione
            self.client.ping()
            logger.info(f"Redis connesso: {host}:{port} (db={db})")
        except redis.ConnectionError as e:
            logger.error(f"Errore connessione Redis: {e}")
            raise
    
    def _make_key(self, date: str) -> str:
        """
        Crea chiave Redis per una data.
        
        Args:
            date: Data in formato YYYY-MM-DD
        
        Returns:
            Chiave Redis completa
        """
        return f"{self.key_prefix}{date}"
    
    def set_metrics(
        self, 
        date: str, 
        metrics: Dict[str, Any]
    ) -> bool:
        """
        Salva metriche in cache con TTL automatico.
        
        Args:
            date: Data in formato YYYY-MM-DD
            metrics: Dictionary con metriche
        
        Returns:
            True se successo, False altrimenti
        """
        try:
            key = self._make_key(date)
            
            # Serializza metriche in JSON
            metrics_json = json.dumps(metrics)
            
            # Salva con TTL
            self.client.setex(
                key,
                self.ttl_seconds,
                metrics_json
            )
            
            logger.debug(f"Metriche cached per {date} con TTL {self.ttl_seconds}s")
            return True
            
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Errore salvataggio cache per {date}: {e}")
            return False
    
    def get_metrics(self, date: str) -> Optional[Dict[str, Any]]:
        """
        Recupera metriche dalla cache.
        
        Args:
            date: Data in formato YYYY-MM-DD
        
        Returns:
            Dictionary con metriche o None se non in cache
        """
        try:
            key = self._make_key(date)
            metrics_json = self.client.get(key)
            
            if metrics_json:
                metrics = json.loads(metrics_json)
                logger.debug(f"Cache HIT per {date}")
                return metrics
            
            logger.debug(f"Cache MISS per {date}")
            return None
            
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Errore lettura cache per {date}: {e}")
            return None
    
    def get_recent_days(self, days: int = 14) -> Dict[str, Dict[str, Any]]:
        """
        Recupera metriche degli ultimi N giorni dalla cache.
        
        Args:
            days: Numero di giorni da recuperare (default: 14)
        
        Returns:
            Dict con date come chiavi e metriche come valori
        """
        result = {}
        today = datetime.now()
        
        for i in range(days):
            date_obj = today - timedelta(days=i)
            date_str = date_obj.strftime('%Y-%m-%d')
            
            metrics = self.get_metrics(date_str)
            if metrics:
                result[date_str] = metrics
        
        logger.info(f"Recuperati {len(result)}/{days} giorni da cache")
        return result
    
    def sync_from_db(self, db, days: int = 14) -> int:
        """
        Sincronizza cache con database SQLite per ultimi N giorni.
        
        Utile per:
        - Popolare cache dopo backfill
        - Ripopolare cache dopo restart Redis
        
        Args:
            db: Istanza GA4Database
            days: Numero di giorni da sincronizzare (default: 14)
        
        Returns:
            Numero di record sincronizzati
        """
        count = 0
        today = datetime.now()
        
        for i in range(days):
            date_obj = today - timedelta(days=i)
            date_str = date_obj.strftime('%Y-%m-%d')
            
            # Recupera da DB
            metrics = db.get_metrics(date_str)
            
            if metrics:
                # Salva in cache (rimuovi extraction_timestamp per cache leggera)
                cache_metrics = {k: v for k, v in metrics.items() if k != 'extraction_timestamp'}
                
                if self.set_metrics(date_str, cache_metrics):
                    count += 1
        
        logger.info(f"Sincronizzati {count}/{days} giorni da DB a Redis")
        return count
    
    def clear_date(self, date: str) -> bool:
        """
        Rimuove una data specifica dalla cache.
        
        Args:
            date: Data in formato YYYY-MM-DD
        
        Returns:
            True se rimosso, False altrimenti
        """
        try:
            key = self._make_key(date)
            deleted = self.client.delete(key)
            logger.info(f"Rimossa data {date} da cache: {deleted > 0}")
            return deleted > 0
        except redis.RedisError as e:
            logger.error(f"Errore rimozione cache per {date}: {e}")
            return False
    
    def clear_all(self) -> int:
        """
        Rimuove tutte le chiavi GA4 dalla cache.
        
        ATTENZIONE: Usa con cautela!
        
        Returns:
            Numero di chiavi rimosse
        """
        try:
            # Trova tutte le chiavi con prefisso
            pattern = f"{self.key_prefix}*"
            keys = self.client.keys(pattern)
            
            if keys:
                deleted = self.client.delete(*keys)
                logger.warning(f"Rimossa intera cache GA4: {deleted} chiavi")
                return deleted
            
            return 0
            
        except redis.RedisError as e:
            logger.error(f"Errore rimozione cache completa: {e}")
            return 0
    
    def get_cached_dates(self) -> List[str]:
        """
        Recupera lista di tutte le date attualmente in cache.
        
        Returns:
            Lista di date in formato YYYY-MM-DD
        """
        try:
            pattern = f"{self.key_prefix}*"
            keys = self.client.keys(pattern)
            
            # Estrai date dai nomi delle chiavi
            dates = []
            for key in keys:
                date = key.replace(self.key_prefix, '')
                dates.append(date)
            
            dates.sort(reverse=True)  # Più recenti prima
            return dates
            
        except redis.RedisError as e:
            logger.error(f"Errore recupero date cached: {e}")
            return []
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Recupera informazioni sullo stato della cache.
        
        Returns:
            Dict con statistiche cache
        """
        try:
            dates = self.get_cached_dates()
            
            info = {
                'cached_days': len(dates),
                'oldest_date': dates[-1] if dates else None,
                'newest_date': dates[0] if dates else None,
                'ttl_seconds': self.ttl_seconds,
                'ttl_days': self.ttl_seconds / (24 * 60 * 60),
                'redis_connected': True
            }
            
            return info
            
        except redis.RedisError as e:
            logger.error(f"Errore recupero info cache: {e}")
            return {
                'cached_days': 0,
                'redis_connected': False,
                'error': str(e)
            }
    
    def test_connection(self) -> bool:
        """
        Testa connessione Redis.
        
        Returns:
            True se connesso, False altrimenti
        """
        try:
            return self.client.ping()
        except redis.RedisError:
            return False
    
    def close(self):
        """Chiude connessione Redis."""
        if hasattr(self, 'client'):
            self.client.close()
            logger.info("Connessione Redis chiusa")
    
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
    
    print("Testing GA4RedisCache...")
    
    try:
        # Test connessione
        cache = GA4RedisCache(db=2)  # Usa db=2 per test
        print(f"✓ Redis connesso: {cache.test_connection()}")
        
        # Test salvataggio
        test_date = "2025-11-01"
        test_metrics = {
            'sessioni_commodity': 150,
            'swi_conversioni': 200,
            'cr_commodity': 133.33
        }
        
        success = cache.set_metrics(test_date, test_metrics)
        print(f"✓ Salvataggio cache: {'OK' if success else 'FAILED'}")
        
        # Test recupero
        metrics = cache.get_metrics(test_date)
        print(f"✓ Recupero cache: {metrics is not None}")
        
        # Test info
        info = cache.get_cache_info()
        print(f"✓ Cache info: {info['cached_days']} giorni cached")
        
        # Cleanup test
        cache.clear_date(test_date)
        
        cache.close()
        print("✓ Test completato")
        
    except redis.ConnectionError as e:
        print(f"✗ Redis non disponibile: {e}")
        print("  Assicurati che Redis sia in esecuzione: redis-server")

