"""
Extraction step implementation.

Handles GA4 data extraction with:
- Automatic date detection (default: yesterday)
- Skip if data already exists
- Force extraction option
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

from backend.ga4_extraction.services import GA4DataService
from backend.workflows.result_types import ExtractionResult, StepStatus


class ExtractionStep:
    """Implementazione step estrazione GA4."""
    
    def __init__(
        self, 
        data_service: GA4DataService,
        logger: Optional[logging.Logger] = None
    ):
        self.data_service = data_service
        self.logger = logger or logging.getLogger(__name__)
    
    def execute(
        self, 
        target_date: Optional[str] = None,
        force: bool = False
    ) -> ExtractionResult:
        """
        Esegue estrazione dati GA4.
        
        Args:
            target_date: Data specifica (None = ieri)
            force: Forza estrazione anche se dati esistono
            
        Returns:
            ExtractionResult con esito operazione
        """
        try:
            self.logger.info(f"Inizio estrazione GA4 (date={target_date}, force={force})")
            
            # PRIMA controlla se dati esistono (per determinare skip)
            check_date = target_date
            if check_date is None:
                check_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            data_existed_before = self.data_service.data_exists_for_date(check_date)
            
            # Esegui estrazione
            if target_date:
                success, extracted_date = self.data_service.extract_and_save_for_date(
                    target_date, force=force
                )
            else:
                success, extracted_date = self.data_service.extract_and_save_for_yesterday(
                    force=force
                )
            
            if not success:
                return ExtractionResult(
                    status=StepStatus.FAILED,
                    message="Estrazione GA4 fallita",
                    error="Errore durante estrazione o salvataggio dati"
                )
            
            # Determina se era skip (dati esistevano prima E non force)
            was_skipped = data_existed_before and not force
            
            return ExtractionResult(
                status=StepStatus.SKIPPED if was_skipped else StepStatus.SUCCESS,
                message=f"Dati {'già presenti' if was_skipped else 'estratti'} per {extracted_date}",
                date=extracted_date,
                records_affected=0 if was_skipped else 1
            )
            
        except Exception as e:
            self.logger.error(f"Errore estrazione: {e}", exc_info=True)
            return ExtractionResult(
                status=StepStatus.FAILED,
                message="Errore durante estrazione",
                error=str(e)
            )

