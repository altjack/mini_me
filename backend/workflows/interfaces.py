"""
Protocol interfaces for workflow steps.

Defines contracts for step implementations using Python Protocol.
Enables dependency injection and testing with mock implementations.
"""

from typing import Protocol, Optional, runtime_checkable
from .result_types import ExtractionResult, GenerationResult, ApprovalResult


@runtime_checkable
class ExtractionStepProtocol(Protocol):
    """Protocollo per step estrazione GA4"""
    
    def execute(
        self, 
        target_date: Optional[str] = None, 
        force: bool = False
    ) -> ExtractionResult:
        """Esegue estrazione dati GA4"""
        ...


@runtime_checkable
class GenerationStepProtocol(Protocol):
    """Protocollo per step generazione email"""
    
    def execute(
        self, 
        skip_data_check: bool = False
    ) -> GenerationResult:
        """Esegue generazione email con AI Agent"""
        ...


@runtime_checkable
class ApprovalStepProtocol(Protocol):
    """Protocollo per step approvazione"""
    
    def execute(
        self, 
        interactive: bool = True
    ) -> ApprovalResult:
        """Esegue approvazione draft"""
        ...

