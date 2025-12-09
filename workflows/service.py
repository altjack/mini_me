"""
Main workflow service for Daily Report.

Orchestrates the complete workflow:
1. GA4 Data Extraction
2. AI Agent Email Generation
3. Draft Approval and Archival

Features:
- Dependency Injection for all steps (testability)
- Context manager for resource management
- Structured logging
- Typed results
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from ga4_extraction.factory import GA4ResourceFactory
from ga4_extraction.services import GA4DataService

from workflows.config import ConfigLoader
from workflows.logging import LoggerFactory
from workflows.result_types import (
    WorkflowResult, 
    ExtractionResult, 
    GenerationResult, 
    ApprovalResult,
    StepStatus,
    StepResult
)
from workflows.interfaces import (
    ExtractionStepProtocol,
    GenerationStepProtocol,
    ApprovalStepProtocol
)
from workflows.steps.extraction import ExtractionStep
from workflows.steps.generation import GenerationStep
from workflows.steps.approval import ApprovalStep


class DailyReportWorkflow:
    """
    Servizio orchestratore per workflow Daily Report.
    
    Caratteristiche:
    - Dependency Injection per tutti gli step (testabilità)
    - Context manager per gestione risorse
    - Logging strutturato
    - Result types tipizzati
    
    Usage:
        # Standard
        config = ConfigLoader.load()
        with DailyReportWorkflow(config) as workflow:
            result = workflow.run_full()
        
        # Con step custom (testing)
        mock_extraction = MockExtractionStep()
        workflow = DailyReportWorkflow(config, extraction_step=mock_extraction)
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
        # Dependency Injection per testing
        extraction_step: Optional[ExtractionStepProtocol] = None,
        generation_step: Optional[GenerationStepProtocol] = None,
        approval_step: Optional[ApprovalStepProtocol] = None,
        # Opzionale: inietta data_service per testing
        data_service: Optional[GA4DataService] = None
    ):
        """
        Inizializza workflow con dipendenze iniettabili.
        
        Args:
            config: Configurazione da config.yaml
            logger: Logger (opzionale, creato automaticamente)
            extraction_step: Step estrazione (opzionale, per testing)
            generation_step: Step generazione (opzionale, per testing)
            approval_step: Step approvazione (opzionale, per testing)
            data_service: Service dati GA4 (opzionale, per testing)
        """
        self.config = config
        self.logger = logger or LoggerFactory.get_logger('workflow', config)
        
        # Gestione risorse
        self._owns_data_service = data_service is None
        if data_service:
            self.data_service = data_service
        else:
            db, cache = GA4ResourceFactory.create_from_config(config)
            self.data_service = GA4DataService(db, cache)
        
        # Inizializza step (DI o default)
        self._extraction = extraction_step or ExtractionStep(
            self.data_service, self.logger
        )
        self._generation = generation_step or GenerationStep(
            config, self.logger
        )
        self._approval = approval_step or ApprovalStep(
            config, self.logger
        )
        
        # Setup directory
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Crea directory necessarie"""
        dirs = [
            self.config['execution']['output_dir'],
            self.config['execution']['archive_dir'],
            'data',
            'logs'
        ]
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)
    
    def run_full(
        self,
        target_date: Optional[str] = None,
        force_extraction: bool = False,
        auto_approve: bool = False
    ) -> WorkflowResult:
        """
        Esegue workflow completo: Extract → Generate → Approve
        
        Args:
            target_date: Data target per estrazione (default: ieri)
            force_extraction: Forza estrazione anche se dati esistono
            auto_approve: Approva automaticamente senza input utente
            
        Returns:
            WorkflowResult con risultati di tutti gli step
        """
        start_time = datetime.now()
        result = WorkflowResult()
        
        try:
            self.logger.info("=== INIZIO WORKFLOW COMPLETO ===")
            
            # Step 1: Estrazione
            extraction = self._extraction.execute(target_date, force_extraction)
            result.steps.append(extraction)
            
            if not extraction.success:
                self.logger.error(f"Estrazione fallita: {extraction.error}")
                return self._finalize_result(result, start_time)
            
            self.logger.info(f"✓ Step 1: {extraction.message}")
            
            # Step 2: Generazione
            generation = self._generation.execute(skip_data_check=True)
            result.steps.append(generation)
            
            if not generation.success:
                self.logger.error(f"Generazione fallita: {generation.error}")
                return self._finalize_result(result, start_time)
            
            self.logger.info(f"✓ Step 2: {generation.message}")
            
            # Step 3: Approvazione
            approval = self._approval.execute(interactive=not auto_approve)
            result.steps.append(approval)
            
            if not approval.success:
                self.logger.warning(f"Approvazione: {approval.message}")
                return self._finalize_result(result, start_time)
            
            self.logger.info(f"✓ Step 3: {approval.message}")
            self.logger.info("=== WORKFLOW COMPLETATO CON SUCCESSO ===")
            
        except Exception as e:
            self.logger.error(f"Errore imprevisto: {e}", exc_info=True)
            # Aggiungi errore come step failed
            result.steps.append(StepResult(
                status=StepStatus.FAILED,
                message="Errore imprevisto nel workflow",
                error=str(e)
            ))
        
        return self._finalize_result(result, start_time)
    
    def _finalize_result(
        self, 
        result: WorkflowResult, 
        start_time: datetime
    ) -> WorkflowResult:
        """Calcola durata e finalizza risultato"""
        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result
    
    # === Metodi di convenienza per singoli step ===
    
    def run_extraction(
        self, 
        target_date: Optional[str] = None,
        force: bool = False
    ) -> ExtractionResult:
        """Esegue solo step estrazione"""
        self.logger.info("=== ESECUZIONE SOLO ESTRAZIONE ===")
        return self._extraction.execute(target_date, force)
    
    def run_generation(self, skip_data_check: bool = False) -> GenerationResult:
        """Esegue solo step generazione"""
        self.logger.info("=== ESECUZIONE SOLO GENERAZIONE ===")
        return self._generation.execute(skip_data_check)
    
    def run_approval(self, interactive: bool = True) -> ApprovalResult:
        """Esegue solo step approvazione"""
        self.logger.info("=== ESECUZIONE SOLO APPROVAZIONE ===")
        return self._approval.execute(interactive)
    
    # === Context Manager ===
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Chiude risorse solo se le possiede"""
        if self._owns_data_service and self.data_service:
            self.data_service.close()
        return False  # Non sopprime eccezioni

