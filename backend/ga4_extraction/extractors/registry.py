"""
Registry per Extractors GA4.

Gestisce la registrazione e il recupero degli extractors disponibili.
"""

from typing import Dict, Optional, List
import logging

from .base import BaseExtractor

logger = logging.getLogger(__name__)

# Registry globale degli extractors
_extractors: Dict[str, BaseExtractor] = {}


def register_extractor(extractor_class: type) -> type:
    """
    Decorator per registrare un extractor nel registry.

    Uso:
        @register_extractor
        class MyExtractor(BaseExtractor):
            name = "my_extractor"
            ...

    Args:
        extractor_class: Classe che estende BaseExtractor

    Returns:
        La classe stessa (permette uso come decorator)
    """
    if not issubclass(extractor_class, BaseExtractor):
        raise TypeError(f"{extractor_class} deve estendere BaseExtractor")

    # Istanzia per validare e ottenere il nome
    instance = extractor_class()
    name = instance.name

    if name in _extractors:
        logger.warning(f"Extractor '{name}' già registrato, sovrascrivo")

    _extractors[name] = instance
    logger.debug(f"Extractor registrato: {name} -> {extractor_class.__name__}")

    return extractor_class


def get_extractor(name: str) -> Optional[BaseExtractor]:
    """
    Ottiene un extractor dal registry per nome.

    Args:
        name: Nome dell'extractor

    Returns:
        Istanza dell'extractor o None se non trovato
    """
    extractor = _extractors.get(name)
    if not extractor:
        logger.warning(f"Extractor '{name}' non trovato. Disponibili: {list(_extractors.keys())}")
    return extractor


def list_extractors() -> List[Dict[str, str]]:
    """
    Lista tutti gli extractors registrati.

    Returns:
        Lista di dict con info sugli extractors:
        [{'name': '...', 'table': '...', 'description': '...', 'delay_days': N}, ...]
    """
    return [
        {
            'name': ext.name,
            'table': ext.table_name,
            'description': ext.description,
            'delay_days': ext.ga4_delay_days
        }
        for ext in _extractors.values()
    ]


def get_all_extractors() -> Dict[str, BaseExtractor]:
    """
    Ottiene tutti gli extractors registrati.

    Returns:
        Dict nome -> istanza extractor
    """
    return _extractors.copy()


# Auto-import degli extractors per registrarli
def _auto_register():
    """Importa automaticamente tutti i moduli extractors per registrarli."""
    try:
        from . import channels
    except ImportError as e:
        logger.debug(f"Impossibile importare channels extractor: {e}")

    try:
        from . import campaigns
    except ImportError as e:
        logger.debug(f"Impossibile importare campaigns extractor: {e}")


# Esegui auto-registrazione all'import del modulo
_auto_register()
