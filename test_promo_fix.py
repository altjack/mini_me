#!/usr/bin/env python3
"""Test script per verificare il fix delle date promozioni."""

import sys
import os
from datetime import datetime

# Aggiungi path
sys.path.append(os.path.dirname(__file__))

from agent.tools import get_active_promos

# Test: 2 dicembre 2025 (ultimo giorno Energy Days)
print("=" * 80)
print("TEST: Promozioni attive il 2 dicembre 2025")
print("=" * 80)
print("\nData test: 2025-12-02 (ultimo giorno 'Energy Days' promo)")
print("Promo nel CSV: Energy Days, 2025-11-26 → 2025-12-02\n")

result = get_active_promos(date="2025-12-02")
print(result)

print("\n" + "=" * 80)
print("TEST: Promozioni attive il 3 dicembre 2025 (giorno dopo)")
print("=" * 80)
print("\nData test: 2025-12-03 (giorno dopo la fine di Energy Days)")
print("Atteso: Nessuna promo attiva\n")

result2 = get_active_promos(date="2025-12-03")
print(result2)
