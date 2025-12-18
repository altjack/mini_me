"""
Sistema di Extractors per dati GA4.

Fornisce un pattern estensibile per aggiungere nuove tipologie di dati
con backfill incrementale automatico.

Uso:
    from backend.ga4_extraction.extractors import get_extractor, list_extractors

    # Lista extractors disponibili
    extractors = list_extractors()

    # Ottieni un extractor specifico
    extractor = get_extractor('channels')

    # Backfill incrementale
    from backend.ga4_extraction.extractors.backfill import incremental_backfill
    result = incremental_backfill('channels')
"""

from .registry import get_extractor, register_extractor, list_extractors
from .base import BaseExtractor

__all__ = [
    'BaseExtractor',
    'get_extractor',
    'register_extractor',
    'list_extractors',
]
