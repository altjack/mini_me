#!/usr/bin/env python3
"""
Service Layer per gestione dati GA4.

Implementa logica business centralizzata seguendo principi SOLID:
- Single Responsibility: ogni metodo ha una responsabilità chiara
- Dependency Injection: DB e Cache iniettati nel costruttore
- Testabilità: facile mockare dipendenze
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Tuple

from .database import GA4Database
from .redis_cache import GA4RedisCache
from .extraction import esegui_giornaliero, save_to_database

logger = logging.getLogger(__name__)


class GA4DataService:
    """
    Service per gestione centralizzata dati GA4.
    
    Responsabilità:
    - Verifica esistenza dati
    - Estrazione con check duplicati
    - Recupero dati con cache-first strategy
    - Coordinamento tra DB e Cache
    """
    
    def __init__(self, db: GA4Database, cache: Optional[GA4RedisCache] = None):
        """
        Inizializza service con dipendenze.
        
        Args:
            db: Istanza GA4Database (obbligatoria)
            cache: Istanza GA4RedisCache (opzionale)
        """
        self.db = db
        self.cache = cache
        logger.info("GA4DataService inizializzato")
    
    def data_exists_for_date(self, date: str, check_products: bool = True) -> bool:
        """
        Verifica se dati esistono già per una data.
        
        Args:
            date: Data in formato YYYY-MM-DD
            check_products: Se verificare anche presenza prodotti
        
        Returns:
            True se dati esistono e sono completi
        """
        return self.db.data_exists(date, check_products=check_products)
    
    def extract_and_save_for_yesterday(self, force: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Estrae e salva dati per ieri con check esistenza.
        
        Args:
            force: Se True, estrae anche se dati esistono già
        
        Returns:
            Tuple (success: bool, date: str|None)
        """
        # Calcola data ieri
        yesterday = datetime.now() - timedelta(days=1)
        target_date = yesterday.strftime('%Y-%m-%d')
        
        return self.extract_and_save_for_date(target_date, force=force)
    
    def extract_and_save_for_date(
        self, 
        target_date: str, 
        force: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Estrae e salva dati per una data specifica con check esistenza.
        
        Args:
            target_date: Data in formato YYYY-MM-DD
            force: Se True, estrae anche se dati esistono già (default: False)
        
        Returns:
            Tuple (success: bool, date: str|None)
            - success: True se operazione completata con successo
            - date: Data estratta se successo, None altrimenti
        
        Example:
            service = GA4DataService(db, cache)
            success, date = service.extract_and_save_for_date('2025-11-10')
            if success:
                print(f"Dati estratti per {date}")
        """
        try:
            # Check esistenza dati (se non force)
            if not force and self.data_exists_for_date(target_date):
                logger.info(f"✓ Dati già presenti per {target_date}, skip estrazione")
                return True, target_date
            
            logger.info(f"Inizio estrazione dati GA4 per {target_date}...")
            
            # Determina tipo estrazione in base alla data
            date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday = today - timedelta(days=1)
            
            if date_obj.date() == yesterday.date():
                extraction_type = 'ieri'
            else:
                extraction_type = target_date
            
            # Esegui estrazione
            results, dates = esegui_giornaliero(extraction_type)
            
            logger.info("✓ Estrazione GA4 completata")
            
            # Salva in database
            actual_date = dates['date_from']
            success = save_to_database(results, actual_date, self.db, self.cache, dates)
            
            if success:
                logger.info(f"✓ Dati salvati in database per {actual_date}")
                return True, actual_date
            else:
                logger.error(f"Errore salvataggio dati per {actual_date}")
                return False, None
                
        except Exception as e:
            logger.error(f"Errore estrazione/salvataggio per {target_date}: {e}", exc_info=True)
            return False, None
    
    def get_data_for_date(
        self, 
        date: str, 
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Recupera dati per una data con cache-first strategy.
        
        Args:
            date: Data in formato YYYY-MM-DD
            use_cache: Se True, prova prima la cache Redis (default: True)
        
        Returns:
            Dictionary con metriche o None se non trovate
        """
        # Prova cache se disponibile e richiesto
        if use_cache and self.cache:
            try:
                cached_data = self.cache.get_metrics(date)
                if cached_data:
                    logger.debug(f"Cache hit per {date}")
                    return cached_data
            except Exception as e:
                logger.warning(f"Errore lettura cache per {date}: {e}")
        
        # Fallback a database
        return self.db.get_metrics(date)
    
    def get_products_for_date(self, date: str) -> list:
        """
        Recupera performance prodotti per una data.
        
        Args:
            date: Data in formato YYYY-MM-DD
        
        Returns:
            Lista di dict con prodotti
        """
        return self.db.get_products(date)
    
    def get_date_range_data(
        self, 
        start_date: str, 
        end_date: str
    ) -> list:
        """
        Recupera dati per un range di date.
        
        Args:
            start_date: Data inizio (YYYY-MM-DD)
            end_date: Data fine (YYYY-MM-DD)
        
        Returns:
            Lista di dict con metriche ordinate per data
        """
        return self.db.get_date_range(start_date, end_date)
    
    def calculate_comparison(
        self, 
        current_date: str, 
        days_ago: int = 7
    ) -> Optional[Dict[str, Any]]:
        """
        Calcola confronto tra data corrente e N giorni prima.
        
        Args:
            current_date: Data corrente (YYYY-MM-DD)
            days_ago: Giorni indietro per confronto (default: 7)
        
        Returns:
            Dict con current, previous e change% per tutte le metriche
        """
        return self.db.calculate_comparison(current_date, days_ago)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Recupera statistiche generali del database.
        
        Returns:
            Dict con statistiche (min_date, max_date, record_count, etc.)
        """
        return self.db.get_statistics()
    
    def close(self):
        """Chiude connessioni a DB e Cache."""
        if self.db:
            self.db.close()
        if self.cache:
            self.cache.close()
        logger.info("GA4DataService chiuso")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


if __name__ == "__main__":
    # Test del service
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("Testing GA4DataService...")
    
    from .factory import GA4ResourceFactory
    
    # Crea risorse
    test_config = {
        'database': {
            'sqlite': {'path': 'data/test_service.db'},
            'redis': {
                'host': 'localhost',
                'port': 6379,
                'db': 1
            }
        }
    }
    
    db, cache = GA4ResourceFactory.create_from_config(test_config)
    
    # Crea service
    with GA4DataService(db, cache) as service:
        # Test check esistenza
        test_date = "2025-11-10"
        exists = service.data_exists_for_date(test_date)
        print(f"✓ Check esistenza per {test_date}: {exists}")
        
        # Test statistiche
        stats = service.get_statistics()
        print(f"✓ Statistiche: {stats['record_count']} record")
    
    print("✓ Test completato")

