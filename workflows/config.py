"""
Configuration management for Daily Report workflow.

Provides centralized configuration loading with:
- YAML file parsing
- Validation
- Caching (LRU)
- Convenience methods for common paths
"""

import os
import yaml
import threading
from functools import lru_cache
from typing import Optional, Dict, Any


class ConfigurationError(Exception):
    """Eccezione per errori di configurazione"""
    pass


class ConfigLoader:
    """
    Gestione centralizzata configurazione.
    
    Singleton pattern con cache LRU per performance.
    Thread-safe per utilizzo in contesti multi-thread.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern per cache configurazione"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def load(config_path: str = "config.yaml") -> dict:
        """
        Carica configurazione da YAML con validazione.

        Args:
            config_path: Percorso file configurazione

        Returns:
            Dizionario configurazione validato

        Raises:
            ConfigurationError: Se file non trovato o non valido
        """
        if not os.path.exists(config_path):
            raise ConfigurationError(
                f"File configurazione non trovato: {config_path}\n"
                "Assicurati che config.yaml sia presente nella directory."
            )

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Errore parsing YAML: {e}")

        # Validazione
        ConfigLoader._validate(config)

        return config
    
    @staticmethod
    @lru_cache(maxsize=4)
    def load_cached(config_path: str = "config.yaml") -> Dict[str, Any]:
        """
        Carica configurazione con caching LRU.
        Usa questa versione per evitare riletture frequenti.
        
        NOTA: Il cache NON si invalida se il file cambia.
        Usa load() se hai bisogno di rilettura.
        """
        return ConfigLoader.load(config_path)

    @staticmethod
    def clear_cache():
        """Invalida cache configurazione"""
        ConfigLoader.load_cached.cache_clear()

    @staticmethod
    def _validate(config: Dict[str, Any]) -> None:
        """
        Valida schema configurazione.
        
        Raises:
            ConfigurationError: Se mancano sezioni o chiavi richieste
        """
        required_sections = {
            'agent': ['model'],
            'database': ['sqlite'],
            'execution': ['output_dir', 'draft_filename', 'archive_dir']
        }
        
        for section, keys in required_sections.items():
            if section not in config:
                raise ConfigurationError(f"Sezione mancante: '{section}'")
            for key in keys:
                if key not in config[section]:
                    raise ConfigurationError(
                        f"Chiave mancante: '{section}.{key}'"
                    )

    # === Metodi di convenienza per estrazione path ===

    @staticmethod
    def get_database_path(config: dict) -> str:
        """Estrae path database da config con default"""
        return config.get('database', {}).get('sqlite', {}).get('path', 'data/ga4_data.db')

    @staticmethod
    def get_draft_path(config: dict) -> str:
        """Estrae path draft da config"""
        output_dir = config['execution']['output_dir']
        draft_filename = config['execution']['draft_filename']
        return os.path.join(output_dir, draft_filename)

    @staticmethod
    def get_archive_dir(config: dict) -> str:
        """Estrae directory archivio da config"""
        return config['execution']['archive_dir']
    
    @staticmethod
    def get_redis_config(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Estrae configurazione Redis da config"""
        return config.get('database', {}).get('redis')

