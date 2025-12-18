"""
Migration Runner per database GA4.

Gestisce l'applicazione di migrations SQL in modo sicuro e tracciato.
Supporta sia SQLite che PostgreSQL.
"""

import os
import glob
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class MigrationRunner:
    """
    Esegue migrations SQL sul database in modo controllato.

    Features:
    - Tracking migrations applicate in tabella _migrations
    - Supporto SQLite e PostgreSQL
    - Esecuzione in transazione per rollback automatico su errore
    - Logging dettagliato
    """

    def __init__(self, conn, db_type: str = 'sqlite'):
        """
        Inizializza il migration runner.

        Args:
            conn: Connessione database (sqlite3.Connection o psycopg2.connection)
            db_type: Tipo database ('sqlite' o 'postgresql')
        """
        self.conn = conn
        self.db_type = db_type
        self._placeholder = '%s' if db_type == 'postgresql' else '?'
        self._migrations_dir = Path(__file__).parent / 'versions'

        # Assicura che la tabella _migrations esista
        self._ensure_migrations_table()

    def _ensure_migrations_table(self):
        """Crea la tabella di tracking migrations se non esiste."""
        cursor = self.conn.cursor()

        if self.db_type == 'postgresql':
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    checksum TEXT
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    version TEXT PRIMARY KEY,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    checksum TEXT
                )
            """)

        self.conn.commit()
        logger.debug("Tabella _migrations verificata/creata")

    def get_applied_migrations(self) -> set:
        """
        Recupera l'elenco delle migrations già applicate.

        Returns:
            Set di nomi file migration già applicati
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT version FROM _migrations ORDER BY version")
        rows = cursor.fetchall()

        # Gestisce sia dict-like rows che tuple
        applied = set()
        for row in rows:
            if isinstance(row, dict):
                applied.add(row['version'])
            else:
                applied.add(row[0])

        return applied

    def get_pending_migrations(self) -> List[Path]:
        """
        Trova migrations non ancora applicate.

        Returns:
            Lista di Path ai file .sql da applicare, ordinati per nome
        """
        applied = self.get_applied_migrations()

        # Trova tutti i file .sql nella directory versions
        all_migrations = sorted(self._migrations_dir.glob('*.sql'))

        # Filtra quelle già applicate
        pending = [m for m in all_migrations if m.name not in applied]

        return pending

    def _calculate_checksum(self, sql_content: str) -> str:
        """Calcola checksum MD5 del contenuto SQL."""
        import hashlib
        return hashlib.md5(sql_content.encode()).hexdigest()

    def apply_migration(self, migration_path: Path) -> Tuple[bool, str]:
        """
        Applica una singola migration in transazione.

        Args:
            migration_path: Path al file .sql

        Returns:
            Tuple (success: bool, message: str)
        """
        version = migration_path.name

        try:
            # Leggi contenuto SQL
            with open(migration_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            if not sql_content.strip():
                return False, f"Migration {version} è vuota"

            checksum = self._calculate_checksum(sql_content)

            cursor = self.conn.cursor()

            # Esegui SQL (può contenere più statement)
            if self.db_type == 'postgresql':
                cursor.execute(sql_content)
            else:
                # SQLite: executescript per multi-statement
                cursor.executescript(sql_content)

            # Registra migration applicata
            ph = self._placeholder
            cursor.execute(
                f"INSERT INTO _migrations (version, checksum) VALUES ({ph}, {ph})",
                (version, checksum)
            )

            self.conn.commit()

            logger.info(f"✓ Migration applicata: {version}")
            return True, f"Migration {version} applicata con successo"

        except Exception as e:
            self.conn.rollback()
            logger.error(f"✗ Errore migration {version}: {e}")
            return False, f"Errore in {version}: {str(e)}"

    def run_all_pending(self) -> Tuple[int, int, List[str]]:
        """
        Applica tutte le migrations pendenti.

        Returns:
            Tuple (applied_count, failed_count, messages)
        """
        pending = self.get_pending_migrations()

        if not pending:
            logger.info("Nessuna migration pendente")
            return 0, 0, ["Nessuna migration da applicare"]

        logger.info(f"Trovate {len(pending)} migrations pendenti")

        applied = 0
        failed = 0
        messages = []

        for migration_path in pending:
            success, message = self.apply_migration(migration_path)
            messages.append(message)

            if success:
                applied += 1
            else:
                failed += 1
                # Stop al primo errore per evitare stato inconsistente
                logger.error(f"Stop migrations a causa di errore in {migration_path.name}")
                break

        return applied, failed, messages

    def get_status(self) -> dict:
        """
        Recupera lo stato corrente delle migrations.

        Returns:
            Dict con informazioni sullo stato
        """
        applied = self.get_applied_migrations()
        pending = self.get_pending_migrations()

        return {
            'applied_count': len(applied),
            'pending_count': len(pending),
            'applied': sorted(applied),
            'pending': [p.name for p in pending]
        }


def run_migrations(conn, db_type: str = 'sqlite', auto_run: bool = True) -> dict:
    """
    Funzione helper per eseguire migrations.

    Usata tipicamente all'avvio dell'applicazione.

    Args:
        conn: Connessione database
        db_type: Tipo database ('sqlite' o 'postgresql')
        auto_run: Se True, applica automaticamente migrations pendenti

    Returns:
        Dict con risultato operazione
    """
    runner = MigrationRunner(conn, db_type)

    if auto_run:
        applied, failed, messages = runner.run_all_pending()
        return {
            'success': failed == 0,
            'applied': applied,
            'failed': failed,
            'messages': messages
        }
    else:
        return runner.get_status()


if __name__ == '__main__':
    # Test standalone
    import sqlite3

    logging.basicConfig(level=logging.INFO)

    # Crea DB di test in memoria
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row

    runner = MigrationRunner(conn, 'sqlite')

    print("Status:", runner.get_status())

    applied, failed, messages = runner.run_all_pending()
    print(f"Applied: {applied}, Failed: {failed}")
    for msg in messages:
        print(f"  - {msg}")

    conn.close()
