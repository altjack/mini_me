"""
Workflows module for Daily Report.

Provides structured workflow orchestration with:
- Typed result types (StepStatus, StepResult, WorkflowResult)
- Configuration management (ConfigLoader)
- Logging factory (LoggerFactory)
- Protocol interfaces (ExtractionStepProtocol, etc.)
- Individual steps (ExtractionStep, GenerationStep, ApprovalStep)
- Main service (DailyReportWorkflow)

Usage:
    from workflows.service import DailyReportWorkflow
    from workflows.config import ConfigLoader
    
    config = ConfigLoader.load()
    with DailyReportWorkflow(config) as workflow:
        result = workflow.run_full()
"""

from workflows.result_types import (
    StepStatus,
    StepResult,
    ExtractionResult,
    GenerationResult,
    ApprovalResult,
    WorkflowResult
)
from workflows.config import ConfigLoader, ConfigurationError
from workflows.logging import LoggerFactory

__all__ = [
    'StepStatus',
    'StepResult',
    'ExtractionResult',
    'GenerationResult',
    'ApprovalResult',
    'WorkflowResult',
    'ConfigLoader',
    'ConfigurationError',
    'LoggerFactory'
]

