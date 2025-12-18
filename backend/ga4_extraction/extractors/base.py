"""
Classe base astratta per Extractors GA4.

Ogni extractor deve estendere questa classe e implementare i metodi astratti.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """
    Classe base per extractors di nuove variabili GA4.

    Per creare un nuovo extractor:
    1. Estendi questa classe
    2. Definisci name, table_name, ga4_delay_days
    3. Implementa extract() e save()
    4. Registra l'extractor nel registry

    Esempio:
        class DevicesExtractor(BaseExtractor):
            name = "devices"
            table_name = "sessions_by_device"
            ga4_delay_days = 2

            def extract(self, client, date):
                # Estrai da GA4
                return [{'device': 'mobile', 'sessions': 100}, ...]

            def save(self, db, date, data):
                # Salva nel DB
                return db.insert_sessions_by_device(date, data)
    """

    # Identificatore unico dell'extractor (deve essere definito nelle sottoclassi)
    name: str = None

    # Nome della tabella di destinazione
    table_name: str = None

    # Ritardo GA4 richiesto in giorni (default: 2 per dimensioni avanzate)
    ga4_delay_days: int = 2

    # Descrizione per UI/help
    description: str = ""

    def __init__(self):
        """Inizializza l'extractor e valida la configurazione."""
        if not self.name:
            raise ValueError(f"{self.__class__.__name__} deve definire 'name'")
        if not self.table_name:
            raise ValueError(f"{self.__class__.__name__} deve definire 'table_name'")

    @abstractmethod
    def extract(self, client, date: str) -> List[Dict[str, Any]]:
        """
        Estrae dati da GA4 per una data specifica.

        Args:
            client: BetaAnalyticsDataClient autenticato
            date: Data in formato YYYY-MM-DD

        Returns:
            Lista di dizionari con i dati estratti.
            Ritorna lista vuota se nessun dato disponibile.

        Raises:
            Exception: Se l'estrazione fallisce
        """
        pass

    @abstractmethod
    def save(self, db, date: str, data: List[Dict[str, Any]]) -> bool:
        """
        Salva i dati estratti nel database.

        Args:
            db: Istanza GA4Database
            date: Data in formato YYYY-MM-DD
            data: Lista di dizionari da salvare

        Returns:
            True se successo, False altrimenti
        """
        pass

    def get_dates_missing(self, db, start_date: str, end_date: str) -> List[str]:
        """
        Trova date che hanno metriche base ma mancano dati per questo extractor.

        Implementazione generica con LEFT JOIN.
        Può essere sovrascritta per logica custom.

        Args:
            db: Istanza GA4Database
            start_date: Data inizio (YYYY-MM-DD)
            end_date: Data fine (YYYY-MM-DD)

        Returns:
            Lista di date mancanti ordinate cronologicamente
        """
        cursor = db.conn.cursor()
        ph = db._placeholder

        # Query generica: date in daily_metrics senza corrispondenza nella tabella target
        query = f"""
            SELECT dm.date
            FROM daily_metrics dm
            LEFT JOIN {self.table_name} t ON dm.date = t.date
            WHERE dm.date BETWEEN {ph} AND {ph}
            GROUP BY dm.date
            HAVING COUNT(t.id) = 0
            ORDER BY dm.date
        """

        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        # Normalizza date come stringhe
        dates = []
        for row in rows:
            date_val = row[0] if not isinstance(row, dict) else row['date']
            if hasattr(date_val, 'isoformat'):
                date_val = date_val.isoformat()
            dates.append(str(date_val))

        return dates

    def validate_date(self, date: str) -> tuple:
        """
        Valida che una data sia valida per l'estrazione.

        Considera il ritardo GA4 richiesto.

        Args:
            date: Data da validare (YYYY-MM-DD)

        Returns:
            Tuple (is_valid: bool, message: str)
        """
        from datetime import datetime, timedelta

        target_date = datetime.strptime(date, '%Y-%m-%d')
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        min_date = today - timedelta(days=self.ga4_delay_days)

        if target_date > min_date:
            days_diff = (today - target_date).days
            return False, (
                f"Data troppo recente ({date}). "
                f"GA4 richiede ~{self.ga4_delay_days * 24}h di ritardo. "
                f"Giorni trascorsi: {days_diff}, richiesti: {self.ga4_delay_days}"
            )

        return True, f"Data valida per estrazione {self.name} ({date})"

    def __repr__(self):
        return f"<{self.__class__.__name__}(name='{self.name}', table='{self.table_name}')>"
