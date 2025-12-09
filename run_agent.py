#!/usr/bin/env python3
"""
Script per eseguire solo la generazione email con AI Agent.

Usage:
    uv run run_agent.py
"""

import sys
import argparse
from typing import Optional

from workflows.service import DailyReportWorkflow
from workflows.config import ConfigLoader, ConfigurationError
from workflows.logging import LoggerFactory
from workflows.result_types import StepStatus


def print_step_result(step_name: str, result) -> None:
    """Stampa risultato di uno step in formato user-friendly"""
    if result.success:
        icon = "✓" if result.status == StepStatus.SUCCESS else "○"  # ○ per SKIPPED
        print(f"{icon} {step_name}: {result.message}")
    else:
        print(f"✗ {step_name}: {result.message}")
        if result.error:
            print(f"  └─ Errore: {result.error}")


def print_summary(
    extraction_result,
    generation_result,
    total_success: bool
) -> None:
    """Stampa riepilogo finale"""
    print()
    print("=" * 60)
    if total_success:
        print("  ✅ GENERAZIONE COMPLETATA")
    else:
        print("  ❌ GENERAZIONE FALLITA")
    print("=" * 60)
    print()
    
    if extraction_result:
        print(f"📊 Dati GA4: {extraction_result.date or 'N/A'}")
    if generation_result and generation_result.draft_path:
        print(f"📧 Draft: {generation_result.draft_path}")
    print()
    
    if total_success:
        print("📝 PROSSIMI PASSI:")
        if generation_result and generation_result.draft_path:
            print(f"   1. Rivedi: cat {generation_result.draft_path}")
        print("   2. Approva: uv run approve_draft.py")
    print()


def run_agent_standalone(
    config: dict,
    target_date: Optional[str] = None,
    force_extraction: bool = False,
    skip_extraction: bool = False
) -> int:
    """
    Esegue workflow estrazione + generazione.
    
    Args:
        config: Configurazione caricata
        target_date: Data target per estrazione (None = ieri)
        force_extraction: Forza estrazione anche se dati esistono
        skip_extraction: Salta estrazione (assume dati già presenti)
        
    Returns:
        Exit code (0 = success, 1 = failure)
    """
    logger = LoggerFactory.get_logger('run_agent', config)
    
    extraction_result = None
    generation_result = None
    
    with DailyReportWorkflow(config, logger=logger) as workflow:
        
        # Step 1: Estrazione (opzionale)
        if not skip_extraction:
            print("📊 Estrazione dati GA4...")
            extraction_result = workflow.run_extraction(
                target_date=target_date,
                force=force_extraction
            )
            print_step_result("Estrazione", extraction_result)
            
            if not extraction_result.success:
                print_summary(extraction_result, None, False)
                return 1
        else:
            print("⏭️  Estrazione saltata (--skip-extraction)")
        
        # Step 2: Generazione
        print("\n🧠 Generazione email con AI Agent...")
        generation_result = workflow.run_generation(
            skip_data_check=skip_extraction
        )
        print_step_result("Generazione", generation_result)
        
        if not generation_result.success:
            print_summary(extraction_result, generation_result, False)
            return 1
    
    # Success
    print_summary(extraction_result, generation_result, True)
    return 0


def main():
    """Entry point CLI"""
    parser = argparse.ArgumentParser(
        description='Generazione email Daily Report con AI Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  uv run run_agent.py                     # Workflow standard
  uv run run_agent.py --date 2025-01-15   # Data specifica  
  uv run run_agent.py --force             # Forza ri-estrazione
  uv run run_agent.py --skip-extraction   # Solo generazione
        """
    )
    parser.add_argument(
        '--date', '-d',
        type=str,
        metavar='YYYY-MM-DD',
        help='Data target per estrazione (default: ieri)'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Forza estrazione anche se dati già presenti'
    )
    parser.add_argument(
        '--skip-extraction', '-s',
        action='store_true',
        help='Salta estrazione GA4 (usa dati esistenti)'
    )
    args = parser.parse_args()
    
    # Header
    print()
    print("=" * 60)
    print("  🤖 DAILY REPORT - Generazione Email")
    print("=" * 60)
    print()
    
    try:
        # Carica configurazione
        print("📋 Caricamento configurazione...")
        config = ConfigLoader.load()
        print("✓ Configurazione caricata\n")
        
        # Esegui workflow
        exit_code = run_agent_standalone(
            config=config,
            target_date=args.date,
            force_extraction=args.force,
            skip_extraction=args.skip_extraction
        )
        sys.exit(exit_code)
        
    except ConfigurationError as e:
        print(f"\n❌ Errore configurazione: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrotto dall'utente")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Errore imprevisto: {e}")
        sys.exit(1)


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================
# Le funzioni seguenti sono mantenute per backward compatibility con codice
# che importa direttamente da run_agent.py. Sono deprecate e verranno rimosse
# in una versione futura.

def load_config(config_path: str = "config.yaml") -> dict:
    """
    DEPRECATED: Usa workflows.config.ConfigLoader.load()
    
    Mantenuto per backward compatibility.
    """
    import warnings
    warnings.warn(
        "run_agent.load_config() is deprecated. "
        "Use workflows.config.ConfigLoader.load() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return ConfigLoader.load(config_path)


def setup_logging(config: dict):
    """
    DEPRECATED: Usa workflows.logging.LoggerFactory.get_logger()
    
    Mantenuto per backward compatibility.
    """
    import warnings
    warnings.warn(
        "run_agent.setup_logging() is deprecated. "
        "Use workflows.logging.LoggerFactory.get_logger() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return LoggerFactory.get_logger('agent', config)


def ensure_directories(config: dict) -> None:
    """
    DEPRECATED: DailyReportWorkflow gestisce le directory automaticamente.
    
    Mantenuto per backward compatibility.
    """
    import warnings
    from pathlib import Path
    warnings.warn(
        "run_agent.ensure_directories() is deprecated. "
        "DailyReportWorkflow handles directories automatically.",
        DeprecationWarning,
        stacklevel=2
    )
    Path(config['execution']['output_dir']).mkdir(parents=True, exist_ok=True)
    Path(config['execution']['archive_dir']).mkdir(parents=True, exist_ok=True)


def run_agent_workflow(
    config: dict,
    logger=None,
    skip_data_check: bool = False
) -> str:
    """
    DEPRECATED: Usa DailyReportWorkflow.run_generation()
    
    Mantenuto per backward compatibility con api.py e altri moduli.
    Verrà rimosso in una versione futura.
    
    Args:
        config: Configurazione
        logger: Logger (ignorato, usa LoggerFactory)
        skip_data_check: Passa a run_generation
        
    Returns:
        Path del draft generato
        
    Raises:
        RuntimeError: Se generazione fallisce
    """
    import warnings
    warnings.warn(
        "run_agent.run_agent_workflow() is deprecated. "
        "Use DailyReportWorkflow.run_generation() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    actual_logger = logger or LoggerFactory.get_logger('agent', config)
    
    # Usa il nuovo workflow service
    with DailyReportWorkflow(config, logger=actual_logger) as workflow:
        result = workflow.run_generation(skip_data_check=skip_data_check)
        
        if not result.success:
            raise RuntimeError(
                f"Generazione fallita: {result.error or result.message}"
            )
        
        return result.draft_path


if __name__ == "__main__":
    main()
