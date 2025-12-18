"""
Extractor per sessioni per campagna marketing.

Estrae breakdown delle sessioni (commodity e luce&gas) per campagna.
"""

from typing import List, Dict, Any
import logging

from .base import BaseExtractor
from .registry import register_extractor

logger = logging.getLogger(__name__)


@register_extractor
class CampaignsExtractor(BaseExtractor):
    """
    Extractor per sessioni suddivise per campagna marketing.

    Tabella: sessions_by_campaign
    Ritardo GA4: 2 giorni (D-2)
    """

    name = "campaigns"
    table_name = "sessions_by_campaign"
    ga4_delay_days = 2
    description = "Sessioni per campagna marketing (commodity e luce&gas)"

    def extract(self, client, date: str) -> List[Dict[str, Any]]:
        """
        Estrae sessioni per campagna da GA4.

        Args:
            client: BetaAnalyticsDataClient
            date: Data YYYY-MM-DD

        Returns:
            Lista di dict: [{'campaign': str, 'commodity_sessions': int, 'lucegas_sessions': int}, ...]
        """
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest
        )
        from backend.ga4_extraction.filters import session_commodity_filter, session_lucegas_filter
        from backend.ga4_extraction.extraction import _execute_ga4_request, PROPERTY_ID

        logger.info(f"Estrazione sessioni per campagna per {date}")

        # Query per sessioni Commodity per campagna
        request_commodity = RunReportRequest(
            property=f'properties/{PROPERTY_ID}',
            dimensions=[Dimension(name="sessionCampaign")],
            metrics=[Metric(name='sessions')],
            date_ranges=[DateRange(start_date=date, end_date=date)],
            dimension_filter=session_commodity_filter()
        )

        commodity_response = _execute_ga4_request(client, request_commodity)

        # Query per sessioni Luce&Gas per campagna
        request_lucegas = RunReportRequest(
            property=f'properties/{PROPERTY_ID}',
            dimensions=[Dimension(name="sessionCampaign")],
            metrics=[Metric(name='sessions')],
            date_ranges=[DateRange(start_date=date, end_date=date)],
            dimension_filter=session_lucegas_filter()
        )

        lucegas_response = _execute_ga4_request(client, request_lucegas)

        # Processa response Commodity
        commodity_data = {}
        if commodity_response.rows:
            for row in commodity_response.rows:
                campaign = row.dimension_values[0].value
                sessions = int(row.metric_values[0].value)
                commodity_data[campaign] = sessions

        # Processa response Luce&Gas
        lucegas_data = {}
        if lucegas_response.rows:
            for row in lucegas_response.rows:
                campaign = row.dimension_values[0].value
                sessions = int(row.metric_values[0].value)
                lucegas_data[campaign] = sessions

        # Combina i dati
        all_campaigns = set(commodity_data.keys()) | set(lucegas_data.keys())

        result = []
        for campaign in sorted(all_campaigns):
            result.append({
                'campaign': campaign,
                'commodity_sessions': commodity_data.get(campaign, 0),
                'lucegas_sessions': lucegas_data.get(campaign, 0)
            })

        logger.info(f"Estratte {len(result)} campagne per {date}")
        return result

    def save(self, db, date: str, data: List[Dict[str, Any]]) -> bool:
        """
        Salva sessioni per campagna nel database.

        Args:
            db: Istanza GA4Database
            date: Data YYYY-MM-DD
            data: Lista di dict con dati campagne

        Returns:
            True se successo
        """
        if not data:
            logger.warning(f"Nessun dato campagna da salvare per {date}")
            return False

        return db.insert_sessions_by_campaign(date, data, replace=True)
