"""
Logger factory for Daily Report workflow.

Provides centralized logger creation with:
- Consistent configuration
- File and console handlers
- Duplicate prevention
- Configurable levels and paths
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Directory log: /tmp su Vercel/Lambda (read-only filesystem), altrimenti locale
_is_serverless = os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME') or __file__.startswith('/var/task')
LOG_DIR = '/tmp/logs' if _is_serverless else 'logs'


class LoggerFactory:
    """
    Factory per creazione logger.
    
    Gestisce correttamente:
    - Creazione nuovi logger
    - Evita duplicazione handler
    - Permette override configurazione
    """
    
    _configured_loggers: Dict[str, logging.Logger] = {}
    
    @classmethod
    def get_logger(
        cls,
        name: str,
        config: Optional[Dict[str, Any]] = None,
        log_file: Optional[str] = None,
        level: Optional[str] = None,
        force_reconfigure: bool = False
    ) -> logging.Logger:
        """
        Ottiene o crea un logger configurato.
        
        Args:
            name: Nome del logger
            config: Configurazione (opzionale se logger già esiste)
            log_file: Override path file log
            level: Override livello log (DEBUG, INFO, WARNING, ERROR)
            force_reconfigure: Se True, riconfigura logger esistente
            
        Returns:
            Logger configurato
        """
        # Se logger esiste e non forziamo riconfigurazione
        if name in cls._configured_loggers and not force_reconfigure:
            return cls._configured_loggers[name]
        
        # Determina configurazione
        log_config = (config or {}).get('logging', {})
        actual_level = level or log_config.get('level', 'INFO')
        actual_file = log_file or log_config.get(f'{name}_log', f'{LOG_DIR}/{name}.log')
        
        # Crea/riconfigura logger
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, actual_level.upper()))
        
        # Rimuovi handler esistenti se riconfigurando
        if force_reconfigure:
            logger.handlers.clear()
        
        # Aggiungi handler solo se non presenti
        if not logger.handlers:
            cls._add_handlers(logger, actual_file, actual_level)
        
        cls._configured_loggers[name] = logger
        return logger
    
    @staticmethod
    def _add_handlers(
        logger: logging.Logger, 
        log_file: str, 
        level: str
    ) -> None:
        """Aggiunge file e console handler"""
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Crea directory log se necessario
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # File handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    @classmethod
    def reset(cls):
        """Reset per testing - rimuove tutti i logger configurati"""
        for logger in cls._configured_loggers.values():
            logger.handlers.clear()
        cls._configured_loggers.clear()

