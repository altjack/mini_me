"""
Modulo per l'estrazione dei dati da Google Analytics 4
"""

from .filters import session_lucegas_filter, session_commodity_filter, funnel_weborder_step1_filter

__all__ = [
    'session_lucegas_filter',
    'session_commodity_filter',
    'funnel_weborder_step1_filter'
]
