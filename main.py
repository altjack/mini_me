#!/usr/bin/env python3
"""
Main orchestrator per Daily Report Workflow.

Usage:
    uv run main.py [--auto-approve]
"""

import sys
import argparse

from workflows.service import DailyReportWorkflow
from workflows.config import ConfigLoader, ConfigurationError
from workflows.result_types import StepStatus


def print_result(result) -> None:
    """Stampa risultato in formato user-friendly"""
    print("\n" + "=" * 70)
    print("  ✅ COMPLETATO" if result.success else "  ❌ FALLITO")
    print("=" * 70)
    
    for i, step in enumerate(result.steps, 1):
        icon = "✓" if step.success else "✗"
        status_label = step.status.name.lower()
        print(f"  {i}. [{icon}] {step.message} ({status_label})")
        if step.error:
            print(f"      └─ Errore: {step.error}")
    
    if result.duration_seconds:
        print(f"\n  ⏱️  Durata: {result.duration_seconds:.1f}s")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Daily Report Workflow Orchestrator'
    )
    parser.add_argument(
        '--auto-approve', 
        action='store_true',
        help='Approva automaticamente senza review'
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Data target (YYYY-MM-DD), default: ieri'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Forza estrazione anche se dati esistono'
    )
    args = parser.parse_args()
    
    print("=" * 70)
    print("  🚀 DAILY REPORT WORKFLOW")
    print("=" * 70 + "\n")
    
    try:
        config = ConfigLoader.load()
        
        with DailyReportWorkflow(config) as workflow:
            result = workflow.run_full(
                target_date=args.date,
                force_extraction=args.force,
                auto_approve=args.auto_approve
            )
            
            print_result(result)
            sys.exit(0 if result.success else 1)
            
    except ConfigurationError as e:
        print(f"❌ Errore configurazione: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Interrotto dall'utente")
        sys.exit(130)


if __name__ == "__main__":
    main()
