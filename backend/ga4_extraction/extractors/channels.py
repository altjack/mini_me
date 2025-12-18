"""
Extractor per sessioni per canale marketing.

Estrae breakdown delle sessioni (commodity e luce&gas) per canale.
"""

from typing import List, Dict, Any
import logging

from .base import BaseExtractor
from .registry import register_extractor

logger = logging.getLogger(__name__)


@register_extractor
class ChannelsExtractor(BaseExtractor):
    """
    Extractor per sessioni suddivise per canale marketing.

    Tabella: sessions_by_channel
    Ritardo GA4: 2 giorni (D-2)
    """

    name = "channels"
    table_name = "sessions_by_channel"
    ga4_delay_days = 2
    description = "Sessioni per canale marketing (commodity e luce&gas)"

    def extract(self, client, date: str) -> List[Dict[str, Any]]:
        """
        Estrae sessioni per canale da GA4.

        Args:
            client: BetaAnalyticsDataClient
            date: Data YYYY-MM-DD

        Returns:
            Lista di dict: [{'channel': str, 'commodity_sessions': int, 'lucegas_sessions': int}, ...]
        """
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest
        )
        from backend.ga4_extraction.filters import session_commodity_filter, session_lucegas_filter
        from backend.ga4_extraction.extraction import _execute_ga4_request, PROPERTY_ID

        logger.info(f"Estrazione sessioni per canale per {date}")

        # Query per sessioni Commodity per canale
        request_commodity = RunReportRequest(
            property=f'properties/{PROPERTY_ID}',
            dimensions=[Dimension(name="sessionCustomChannelGroup:5896515461")],
            metrics=[Metric(name='sessions')],
            date_ranges=[DateRange(start_date=date, end_date=date)],
            dimension_filter=session_commodity_filter()
        )

        commodity_response = _execute_ga4_request(client, request_commodity)

        # Query per sessioni Luce&Gas per canale
        request_lucegas = RunReportRequest(
            property=f'properties/{PROPERTY_ID}',
            dimensions=[Dimension(name="sessionCustomChannelGroup:5896515461")],
            metrics=[Metric(name='sessions')],
            date_ranges=[DateRange(start_date=date, end_date=date)],
            dimension_filter=session_lucegas_filter()
        )

        lucegas_response = _execute_ga4_request(client, request_lucegas)

        # Processa response Commodity
        commodity_data = {}
        if commodity_response.rows:
            for row in commodity_response.rows:
                channel = row.dimension_values[0].value
                sessions = int(row.metric_values[0].value)
                commodity_data[channel] = sessions

        # Processa response Luce&Gas
        lucegas_data = {}
        if lucegas_response.rows:
            for row in lucegas_response.rows:
                channel = row.dimension_values[0].value
                sessions = int(row.metric_values[0].value)
                lucegas_data[channel] = sessions

        # Combina i dati
        all_channels = set(commodity_data.keys()) | set(lucegas_data.keys())

        result = []
        for channel in sorted(all_channels):
            result.append({
                'channel': channel,
                'commodity_sessions': commodity_data.get(channel, 0),
                'lucegas_sessions': lucegas_data.get(channel, 0)
            })

        logger.info(f"Estratti {len(result)} canali per {date}")
        return result

    def save(self, db, date: str, data: List[Dict[str, Any]]) -> bool:
        """
        Salva sessioni per canale nel database.

        Args:
            db: Istanza GA4Database
            date: Data YYYY-MM-DD
            data: Lista di dict con dati canali

        Returns:
            True se successo
        """
        if not data:
            logger.warning(f"Nessun dato canale da salvare per {date}")
            return False

        return db.insert_sessions_by_channel(date, data, replace=True)
