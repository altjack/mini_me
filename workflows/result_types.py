"""
Result types for workflow steps.

Provides typed results for each workflow step with:
- StepStatus enum for step outcomes
- Immutable StepResult base class
- Specialized result types (ExtractionResult, GenerationResult, ApprovalResult)
- WorkflowResult for aggregated results
"""

from dataclasses import dataclass, field
from typing import Optional, List, Type, TypeVar
from datetime import datetime
from enum import Enum, auto


class StepStatus(Enum):
    """Stati possibili di uno step"""
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()  # Dati già presenti, estrazione non necessaria


@dataclass(frozen=True)
class StepResult:
    """
    Risultato base di uno step.
    
    Attributes:
        status: Stato dello step (SUCCESS, FAILED, SKIPPED)
        message: Messaggio descrittivo
        error: Dettaglio errore se fallito
        timestamp: Timestamp esecuzione
    """
    status: StepStatus
    message: str
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def success(self) -> bool:
        """Convenienza: True se SUCCESS o SKIPPED"""
        return self.status in (StepStatus.SUCCESS, StepStatus.SKIPPED)


@dataclass(frozen=True)
class ExtractionResult(StepResult):
    """
    Risultato step estrazione GA4.
    
    Attributes:
        date: Data per cui sono stati estratti i dati
        records_affected: Numero di record estratti
    """
    date: Optional[str] = None
    records_affected: int = 0


@dataclass(frozen=True)
class GenerationResult(StepResult):
    """
    Risultato step generazione email.
    
    Attributes:
        draft_path: Percorso al file draft generato
    """
    draft_path: Optional[str] = None


@dataclass(frozen=True)
class ApprovalResult(StepResult):
    """
    Risultato step approvazione.
    
    Attributes:
        archive_path: Percorso al file archiviato
        added_to_memory: Se aggiunto a Redis memory
    """
    archive_path: Optional[str] = None
    added_to_memory: bool = False


# TypeVar per metodo generico get_step
T = TypeVar('T', bound=StepResult)


@dataclass
class WorkflowResult:
    """
    Risultato aggregato workflow completo.
    
    Attributes:
        steps: Lista dei risultati di ogni step
        duration_seconds: Durata totale workflow
    """
    steps: List[StepResult] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    @property
    def success(self) -> bool:
        """True se tutti gli step hanno avuto successo"""
        return all(step.success for step in self.steps) if self.steps else False
    
    @property
    def errors(self) -> List[str]:
        """Lista errori da tutti gli step"""
        return [s.error for s in self.steps if s.error]
    
    def get_step(self, step_type: Type[T]) -> Optional[T]:
        """Recupera risultato di uno step specifico per tipo"""
        for step in self.steps:
            if isinstance(step, step_type):
                return step
        return None
    
    @property
    def extraction(self) -> Optional[ExtractionResult]:
        """Shortcut per risultato estrazione"""
        return self.get_step(ExtractionResult)
    
    @property
    def generation(self) -> Optional[GenerationResult]:
        """Shortcut per risultato generazione"""
        return self.get_step(GenerationResult)
    
    @property
    def approval(self) -> Optional[ApprovalResult]:
        """Shortcut per risultato approvazione"""
        return self.get_step(ApprovalResult)

