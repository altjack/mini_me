#!/usr/bin/env python3
"""
Script di test per validazione date canali GA4.

Testa la nuova funzione validate_date_for_channels() con vari scenari.

Usage:
    uv run test_date_validation.py
"""

import sys
import os
from datetime import datetime, timedelta

# Aggiungi directory parent al path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ga4_extraction.extraction import validate_date_for_channels


def test_validation():
    """Testa validazione date con vari scenari."""
    
    print("=" * 80)
    print("  🧪 TEST VALIDAZIONE DATE CANALI GA4")
    print("=" * 80)
    print()
    
    today = datetime.now()
    
    # Scenari di test
    test_cases = [
        ("D-0 (oggi)", (today - timedelta(days=0)).strftime('%Y-%m-%d'), False),
        ("D-1 (ieri)", (today - timedelta(days=1)).strftime('%Y-%m-%d'), False),
        ("D-2 (2 giorni fa)", (today - timedelta(days=2)).strftime('%Y-%m-%d'), True),
        ("D-3 (3 giorni fa)", (today - timedelta(days=3)).strftime('%Y-%m-%d'), True),
        ("D-7 (1 settimana fa)", (today - timedelta(days=7)).strftime('%Y-%m-%d'), True),
        ("D-30 (1 mese fa)", (today - timedelta(days=30)).strftime('%Y-%m-%d'), True),
    ]
    
    print("📅 Test Validazione Date:\n")
    
    passed = 0
    failed = 0
    
    for label, date_str, expected_valid in test_cases:
        is_valid, message = validate_date_for_channels(date_str)
        
        # Verifica risultato
        if is_valid == expected_valid:
            status = "✓ PASS"
            passed += 1
        else:
            status = "✗ FAIL"
            failed += 1
        
        # Output
        valid_str = "VALIDA" if is_valid else "NON VALIDA"
        print(f"{status:10} {label:20} ({date_str})")
        print(f"           Status: {valid_str}")
        print(f"           {message}")
        print()
    
    # Riepilogo
    print("=" * 80)
    print("  📊 RIEPILOGO TEST")
    print("=" * 80)
    print()
    print(f"Test superati: {passed}/{len(test_cases)}")
    print(f"Test falliti:  {failed}/{len(test_cases)}")
    print()
    
    if failed == 0:
        print("🎉 Tutti i test sono passati!")
        print()
        print("✅ La validazione funziona correttamente:")
        print("   • D-0 e D-1: NON VALIDE (come previsto)")
        print("   • D-2 e oltre: VALIDE (come previsto)")
        print()
        return 0
    else:
        print("⚠️  Alcuni test sono falliti. Controlla la logica di validazione.")
        print()
        return 1


def test_edge_cases():
    """Testa casi limite."""
    
    print("=" * 80)
    print("  🧪 TEST CASI LIMITE")
    print("=" * 80)
    print()
    
    # Test con min_delay_days personalizzato
    today = datetime.now()
    d3 = (today - timedelta(days=3)).strftime('%Y-%m-%d')
    
    print("Test con min_delay_days=3 (invece di default 2):\n")
    
    is_valid, message = validate_date_for_channels(d3, min_delay_days=3)
    print(f"Data: {d3} (D-3)")
    print(f"Min delay: 3 giorni")
    print(f"Risultato: {'VALIDA' if is_valid else 'NON VALIDA'}")
    print(f"Messaggio: {message}")
    print()
    
    # Test con D-2 e min_delay_days=3 (dovrebbe essere non valida)
    d2 = (today - timedelta(days=2)).strftime('%Y-%m-%d')
    is_valid, message = validate_date_for_channels(d2, min_delay_days=3)
    print(f"Data: {d2} (D-2)")
    print(f"Min delay: 3 giorni")
    print(f"Risultato: {'VALIDA' if is_valid else 'NON VALIDA'}")
    print(f"Messaggio: {message}")
    print()
    
    print("✓ Test casi limite completato")
    print()


if __name__ == '__main__':
    print()
    
    # Test principale
    result1 = test_validation()
    
    # Test casi limite
    test_edge_cases()
    
    sys.exit(result1)

