"""
Configurazione centralizzata per l'applicazione GA4 Data Pipeline.

Single source of truth per tutti i parametri configurabili.
Carica da config.yaml con override da variabili ambiente.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class GA4Config:
    """Configurazione per GA4 API."""

    property_id: str = ""
    rate_limit_rps: int = 9  # Sotto il limite GA4 di 10 rps
    retry_max_attempts: int = 3
    retry_base_delay: float = 2.0  # Secondi
    retry_max_delay: float = 60.0  # Secondi
    channel_delay_days: int = 2  # D-2 per dati canali/campagne
    request_timeout: float = 30.0  # Timeout singola richiesta


@dataclass
class CacheConfig:
    """Configurazione per Redis cache."""

    enabled: bool = True
    ttl_days: int = 21  # TTL cache metriche
    host: str = "localhost"
    port: int = 6379
    db: int = 1
    key_prefix: str = "ga4:metrics:"
    redis_url: Optional[str] = None  # Override completo URL


@dataclass
class DatabaseConfig:
    """Configurazione database."""

    sqlite_path: str = "data/ga4_data.db"
    run_migrations: bool = True
    backup_enabled: bool = True
    backup_dir: str = "data/backups"


@dataclass
class LoggingConfig:
    """Configurazione logging."""

    level: str = "INFO"
    log_dir: str = "logs"
    format: str = "%(asctime)s - %(levelname)s - %(message)s"


@dataclass
class AppConfig:
    """Configurazione principale dell'applicazione."""

    ga4: GA4Config = field(default_factory=GA4Config)
    cache: CacheConfig = field(default_factory=CacheConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "AppConfig":
        """
        Carica configurazione da YAML + env vars.

        Priorità:
        1. Variabili ambiente (massima priorità)
        2. File config.yaml
        3. Valori default

        Args:
            config_path: Path al file config.yaml. Se None, cerca in ordini:
                        - ./config.yaml
                        - ../config.yaml (dalla directory backend)

        Returns:
            Istanza AppConfig configurata
        """
        yaml_config = {}

        # Cerca config.yaml
        if config_path is None:
            possible_paths = [
                Path("config.yaml"),
                Path(__file__).parent.parent.parent / "config.yaml",  # Root progetto
            ]
            for p in possible_paths:
                if p.exists():
                    config_path = str(p)
                    break

        # Carica YAML se trovato
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, "r") as f:
                    yaml_config = yaml.safe_load(f) or {}
                logger.debug(f"Configurazione caricata da {config_path}")
            except Exception as e:
                logger.warning(f"Errore caricamento {config_path}: {e}")

        # Costruisci config con override env vars
        return cls(
            ga4=cls._load_ga4_config(yaml_config),
            cache=cls._load_cache_config(yaml_config),
            database=cls._load_database_config(yaml_config),
            logging=cls._load_logging_config(yaml_config),
        )

    @classmethod
    def _load_ga4_config(cls, yaml_config: dict) -> GA4Config:
        """Carica configurazione GA4."""
        ga4_yaml = yaml_config.get("ga4_extraction", {})

        return GA4Config(
            property_id=os.getenv("GA4_PROPERTY_ID", os.getenv("PROPERTY_ID", "")),
            rate_limit_rps=int(os.getenv("GA4_RATE_LIMIT_RPS", 9)),
            retry_max_attempts=int(os.getenv("GA4_RETRY_MAX_ATTEMPTS", 3)),
            retry_base_delay=float(os.getenv("GA4_RETRY_BASE_DELAY", 2.0)),
            retry_max_delay=float(os.getenv("GA4_RETRY_MAX_DELAY", 60.0)),
            channel_delay_days=int(
                os.getenv("GA4_CHANNEL_DELAY_DAYS", ga4_yaml.get("channel_delay_days", 2))
            ),
            request_timeout=float(os.getenv("GA4_REQUEST_TIMEOUT", 30.0)),
        )

    @classmethod
    def _load_cache_config(cls, yaml_config: dict) -> CacheConfig:
        """Carica configurazione cache."""
        # Supporta sia database.redis che redis (legacy)
        redis_yaml = yaml_config.get("database", {}).get("redis", {})
        if not redis_yaml:
            redis_yaml = yaml_config.get("redis", {})

        return CacheConfig(
            enabled=os.getenv("CACHE_ENABLED", "true").lower() == "true",
            ttl_days=int(os.getenv("CACHE_TTL_DAYS", redis_yaml.get("ttl_days", 21))),
            host=os.getenv("REDIS_HOST", redis_yaml.get("host", "localhost")),
            port=int(os.getenv("REDIS_PORT", redis_yaml.get("port", 6379))),
            db=int(os.getenv("REDIS_DB", redis_yaml.get("db", 1))),
            key_prefix=os.getenv("REDIS_KEY_PREFIX", redis_yaml.get("key_prefix", "ga4:metrics:")),
            redis_url=os.getenv("REDIS_URL"),
        )

    @classmethod
    def _load_database_config(cls, yaml_config: dict) -> DatabaseConfig:
        """Carica configurazione database."""
        db_yaml = yaml_config.get("database", {}).get("sqlite", {})

        return DatabaseConfig(
            sqlite_path=os.getenv("SQLITE_PATH", db_yaml.get("path", "data/ga4_data.db")),
            run_migrations=os.getenv("DB_RUN_MIGRATIONS", "true").lower() == "true",
            backup_enabled=db_yaml.get("backup_enabled", True),
            backup_dir=db_yaml.get("backup_dir", "data/backups"),
        )

    @classmethod
    def _load_logging_config(cls, yaml_config: dict) -> LoggingConfig:
        """Carica configurazione logging."""
        log_yaml = yaml_config.get("logging", {})

        return LoggingConfig(
            level=os.getenv("LOG_LEVEL", log_yaml.get("level", "INFO")),
            log_dir=log_yaml.get("log_dir", "logs"),
            format=log_yaml.get("format", "%(asctime)s - %(levelname)s - %(message)s"),
        )


# Singleton per accesso globale
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """
    Ottiene l'istanza singleton della configurazione.

    Returns:
        AppConfig configurata
    """
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config


def reload_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Ricarica la configurazione (utile per test).

    Args:
        config_path: Path opzionale al file config

    Returns:
        Nuova istanza AppConfig
    """
    global _config
    _config = AppConfig.load(config_path)
    return _config


if __name__ == "__main__":
    # Test standalone
    logging.basicConfig(level=logging.DEBUG)

    config = get_config()
    print(f"GA4 Config: {config.ga4}")
    print(f"Cache Config: {config.cache}")
    print(f"Database Config: {config.database}")
    print(f"Logging Config: {config.logging}")
