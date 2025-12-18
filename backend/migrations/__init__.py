"""
Sistema di migrations per il database GA4.

Permette l'evoluzione dello schema in modo controllato e tracciato.
"""

from .runner import MigrationRunner, run_migrations

__all__ = ['MigrationRunner', 'run_migrations']
