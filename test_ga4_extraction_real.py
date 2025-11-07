#!/usr/bin/env python3
"""
Test estrazione GA4 con credenziali REALI.

Questo script testa:
1. Connessione GA4 con credenziali reali
2. Estrazione dati per data specifica
3. Validazione tipi di dati (int/float)
4. Verifica che non ci siano timeout
5. Verifica che i valori non siano 0 o null

ATTENZIONE: 
- NON salva dati in database
- Usa credenziali reali GA4
- Utile per testare nuove query prima di integrarle

Usage:
    python test_ga4_extraction_real.py [--date YYYY-MM-DD]
"""

import sys
import os
import argparse
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Aggiungi directory corrente al path
sys.path.insert(0, os.path.dirname(__file__))

from ga4_extraction.extraction import (
    calculate_dates,
    sessions,
    session_commodity_filter,
    session_lucegas_filter,
    giornaliero_swi,
    calculate_cr,
    giornaliero_prodotti,
    giornaliero_startfunnel,
    giornaliero_cr_canalizzazione,
    daily_sessions_channels,
    SWI_per_commodity_type,
    client
)


class Colors:
    """ANSI color codes."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(title: str):
    """Stampa header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.RESET}\n")


def print_result(name: str, value: Any, expected_type: str = None, required: bool = True):
    """
    Stampa risultato con validazione.
    
    Args:
        name: Nome metrica
        value: Valore estratto
        expected_type: Tipo atteso ('int' o 'float')
        required: Se True, fallisce se valore è None/0
    """
    # Check null/None
    if value is None:
        status = f"{Colors.RED}✗ NULL{Colors.RESET}"
        print(f"{status} {name}: None")
        return False
    
    # Check tipo
    type_ok = True
    if expected_type == 'int':
        type_ok = isinstance(value, (int, float)) and value == int(value)
        value = int(value)
    elif expected_type == 'float':
        type_ok = isinstance(value, (int, float))
        value = float(value)
    
    # Check zero (se required)
    if required and value == 0:
        status = f"{Colors.YELLOW}⚠ ZERO{Colors.RESET}"
        print(f"{status} {name}: {value} (tipo: {type(value).__name__})")
        return False
    
    # Tutto ok
    if type_ok:
        status = f"{Colors.GREEN}✓ OK{Colors.RESET}"
    else:
        status = f"{Colors.RED}✗ TYPE{Colors.RESET}"
    
    # Formatta valore
    if expected_type == 'float' and isinstance(value, float):
        value_str = f"{value:.2f}"
    else:
        value_str = str(value)
    
    print(f"{status}   {name}: {value_str} (tipo: {type(value).__name__})")
    return type_ok


def validate_int_result(result: int, name: str) -> bool:
    """
    Valida risultato int (sessioni, conversioni, ecc.).
    
    Returns:
        True se valido, False altrimenti
    """
    if result is None:
        print(f"{Colors.RED}✗ INVALID{Colors.RESET} {name}: Result None")
        return False
    
    if not isinstance(result, (int, float)):
        print(f"{Colors.RED}✗ INVALID{Colors.RESET} {name}: Tipo non valido ({type(result).__name__})")
        return False
    
    print(f"\n{Colors.CYAN}📊 {name}{Colors.RESET}")
    
    valid = print_result(
        "  Valore", 
        int(result),
        expected_type='int',
        required=True
    )
    
    return valid


def validate_float_result(result: float, name: str) -> bool:
    """
    Valida risultato float (CR, ecc.).
    
    Returns:
        True se valido, False altrimenti
    """
    if result is None:
        print(f"{Colors.RED}✗ INVALID{Colors.RESET} {name}: Result None")
        return False
    
    if not isinstance(result, (int, float)):
        print(f"{Colors.RED}✗ INVALID{Colors.RESET} {name}: Tipo non valido ({type(result).__name__})")
        return False
    
    print(f"\n{Colors.CYAN}📊 {name}{Colors.RESET}")
    
    valid = print_result(
        "  Valore (%)", 
        float(result),
        expected_type='float',
        required=False  # CR può essere 0
    )
    
    return valid


def validate_products(result, total_swi: int) -> bool:
    """Valida risultato prodotti."""
    import pandas as pd
    
    if result is None:
        print(f"{Colors.RED}✗ INVALID{Colors.RESET} Prodotti: None")
        return False
    
    if not isinstance(result, pd.DataFrame):
        print(f"{Colors.RED}✗ INVALID{Colors.RESET} Prodotti: Non è un DataFrame")
        return False
    
    if result.empty:
        print(f"{Colors.YELLOW}⚠ EMPTY{Colors.RESET} Prodotti: DataFrame vuoto")
        return False
    
    print(f"\n{Colors.CYAN}📊 PRODOTTI{Colors.RESET}")
    print(f"  Prodotti trovati: {len(result)}")
    print(f"  Colonne: {list(result.columns)}")
    print()
    
    # Valida ogni prodotto
    all_valid = True
    total_conversions_sum = 0
    
    for idx, row in result.iterrows():
        product = row.get('Product', 'Unknown')
        total = row.get('Total', 0)
        percentage_str = row.get('Percentage', '0%')
        
        # Rimuovi % e converti
        try:
            percentage = float(percentage_str.replace('%', ''))
        except:
            percentage = 0.0
        
        total_conversions_sum += total
        
        # Stampa prodotto
        print(f"  • {product}")
        valid_total = print_result(
            "    Total conversions",
            total,
            expected_type='float',
            required=False  # Alcuni prodotti possono essere 0
        )
        valid_perc = print_result(
            "    Percentage",
            percentage,
            expected_type='float',
            required=False
        )
        
        all_valid = all_valid and valid_total and valid_perc
    
    # Verifica somma totale
    print()
    diff = abs(total_conversions_sum - total_swi)
    if diff > 5:  # Tolleranza di 5 per arrotondamenti
        print(f"{Colors.YELLOW}⚠ WARNING{Colors.RESET} Somma conversioni prodotti ({total_conversions_sum:.0f}) != Total SWI ({total_swi})")
    else:
        print(f"{Colors.GREEN}✓ OK{Colors.RESET}       Somma conversioni prodotti corrisponde a SWI (diff: {diff:.1f})")
    
    return all_valid


def validate_cr_canalizzazione(result) -> Optional[float]:
    """Valida CR canalizzazione e ritorna valore."""
    import pandas as pd
    
    if result is None or not isinstance(result, pd.DataFrame) or result.empty:
        print(f"{Colors.RED}✗ INVALID{Colors.RESET} CR Canalizzazione: Result non valido")
        return None
    
    print(f"\n{Colors.CYAN}📊 CR CANALIZZAZIONE{Colors.RESET}")
    
    try:
        value_str = result.iloc[0]['Value']
        value = float(value_str.replace('%', ''))
        
        print_result(
            "  CR Canalizzazione (%)",
            value,
            expected_type='float',
            required=False
        )
        
        return value
    except Exception as e:
        print(f"{Colors.RED}✗ ERROR{Colors.RESET} Parsing CR Canalizzazione: {e}")
        return None


def validate_sessions_channels(result) -> bool:
    """Valida risultato sessioni per canale."""
    import pandas as pd
    
    if result is None:
        print(f"{Colors.RED}✗ INVALID{Colors.RESET} Sessioni Canali: None")
        return False
    
    if not isinstance(result, pd.DataFrame):
        print(f"{Colors.RED}✗ INVALID{Colors.RESET} Sessioni Canali: Non è un DataFrame")
        return False
    
    if result.empty:
        print(f"{Colors.YELLOW}⚠ EMPTY{Colors.RESET} Sessioni Canali: DataFrame vuoto")
        return False
    
    print(f"\n{Colors.CYAN}📊 SESSIONI PER CANALE{Colors.RESET}")
    
    # Verifica colonne richieste
    required_cols = ['Channel', 'Commodity_Sessions', 'LuceGas_Sessions']
    
    missing_cols = [col for col in required_cols if col not in result.columns]
    if missing_cols:
        print(f"{Colors.RED}✗ MISSING COLUMNS{Colors.RESET}: {missing_cols}")
        return False
    
    print(f"  Canali trovati: {len(result)}")
    print(f"  Colonne: {list(result.columns)}")
    print()
    
    # Valida ogni canale
    all_valid = True
    
    for idx, row in result.iterrows():
        channel = row['Channel']
        print(f"  {Colors.BOLD}• {channel}{Colors.RESET}")
        
        # Valida Commodity
        valid_comm = print_result(
            "    Commodity Sessions",
            row['Commodity_Sessions'],
            expected_type='int',
            required=False
        )
        
        # Valida Luce&Gas
        valid_lg = print_result(
            "    Luce&Gas Sessions",
            row['LuceGas_Sessions'],
            expected_type='int',
            required=False
        )
        
        all_valid = all_valid and valid_comm and valid_lg
        print()
    
    return all_valid


def validate_commodity_type(result) -> bool:
    """Valida risultato SWI per commodity type."""
    import pandas as pd
    
    if result is None:
        print(f"{Colors.RED}✗ INVALID{Colors.RESET} SWI Commodity Type: None")
        return False
    
    if not isinstance(result, pd.DataFrame):
        print(f"{Colors.RED}✗ INVALID{Colors.RESET} SWI Commodity Type: Non è un DataFrame")
        return False
    
    if result.empty:
        print(f"{Colors.YELLOW}⚠ EMPTY{Colors.RESET} SWI Commodity Type: DataFrame vuoto")
        return False
    
    print(f"\n{Colors.CYAN}📊 SWI PER COMMODITY TYPE{Colors.RESET}")
    
    # Verifica colonne richieste
    required_cols = ['Commodity_Type', 'Conversions']
    
    missing_cols = [col for col in required_cols if col not in result.columns]
    if missing_cols:
        print(f"{Colors.RED}✗ MISSING COLUMNS{Colors.RESET}: {missing_cols}")
        return False
    
    print(f"  Commodity types trovati: {len(result)}")
    print(f"  Colonne: {list(result.columns)}")
    print()
    
    # Valida ogni commodity type
    all_valid = True
    total_conversions = 0
    
    for idx, row in result.iterrows():
        commodity_type = row['Commodity_Type']
        print(f"  {Colors.BOLD}• {commodity_type.upper()}{Colors.RESET}")
        
        valid = print_result(
            "    Conversions",
            row['Conversions'],
            expected_type='int',
            required=False
        )
        
        all_valid = all_valid and valid
        total_conversions += row['Conversions']
        print()
    
    print(f"  {Colors.BOLD}Totale conversioni:{Colors.RESET} {total_conversions}")
    print()
    
    return all_valid


def test_extraction(target_date: str = None):
    """
    Test completo estrazione GA4.
    
    Args:
        target_date: Data da estrarre (YYYY-MM-DD), default = ieri
    """
    print(f"{Colors.BOLD}")
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║         TEST ESTRAZIONE GA4 - Credenziali REALI                  ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")
    
    # Calcola date
    if target_date:
        try:
            target_dt = datetime.strptime(target_date, '%Y-%m-%d')
        except ValueError:
            print(f"{Colors.RED}✗ Errore: Data non valida. Usa formato YYYY-MM-DD{Colors.RESET}")
            return 1
    else:
        # Default: ieri
        target_dt = datetime.now() - timedelta(days=1)
        target_date = target_dt.strftime('%Y-%m-%d')
    
    print(f"\n{Colors.BOLD}📅 PERIODO TEST:{Colors.RESET}")
    print(f"   Data estrazione:  {target_date}")
    print()
    
    results_summary = {
        'passed': 0,
        'failed': 0,
        'warnings': 0
    }
    
    # ========== TEST 1: Sessioni Commodity ==========
    print_header("TEST 1: Sessioni Commodity")
    
    try:
        start_time = time.time()
        result = sessions(client, target_date, session_commodity_filter())
        elapsed = time.time() - start_time
        
        print(f"⏱️  Tempo esecuzione: {elapsed:.2f}s")
        
        if elapsed > 30:
            print(f"{Colors.YELLOW}⚠ WARNING{Colors.RESET} Timeout vicino (>30s)")
            results_summary['warnings'] += 1
        
        if validate_int_result(result, "Sessioni Commodity"):
            results_summary['passed'] += 1
        else:
            results_summary['failed'] += 1
        
        sessioni = result
        
    except Exception as e:
        print(f"{Colors.RED}✗ ERRORE{Colors.RESET} Estrazione fallita: {e}")
        results_summary['failed'] += 1
        return 1
    
    # ========== TEST 2: Sessioni Luce&Gas ==========
    print_header("TEST 2: Sessioni Luce&Gas")
    
    try:
        start_time = time.time()
        result = sessions(client, target_date, session_lucegas_filter())
        elapsed = time.time() - start_time
        
        print(f"⏱️  Tempo esecuzione: {elapsed:.2f}s")
        
        if elapsed > 30:
            print(f"{Colors.YELLOW}⚠ WARNING{Colors.RESET} Timeout vicino (>30s)")
            results_summary['warnings'] += 1
        
        if validate_int_result(result, "Sessioni Luce&Gas"):
            results_summary['passed'] += 1
        else:
            results_summary['failed'] += 1
        
        sessioni_lucegas = result
        
    except Exception as e:
        print(f"{Colors.RED}✗ ERRORE{Colors.RESET} Estrazione fallita: {e}")
        results_summary['failed'] += 1
        return 1
    
    # ========== TEST 3: Sessioni per Canale ==========
    print_header("TEST 3: Sessioni per Canale (Spaccato)")
    
    try:
        start_time = time.time()
        result = daily_sessions_channels(client, target_date)
        elapsed = time.time() - start_time
        
        print(f"⏱️  Tempo esecuzione: {elapsed:.2f}s")
        
        if elapsed > 30:
            print(f"{Colors.YELLOW}⚠ WARNING{Colors.RESET} Timeout vicino (>30s)")
            results_summary['warnings'] += 1
        
        if validate_sessions_channels(result):
            results_summary['passed'] += 1
        else:
            results_summary['failed'] += 1
        
    except Exception as e:
        print(f"{Colors.RED}✗ ERRORE{Colors.RESET} Estrazione fallita: {e}")
        results_summary['failed'] += 1
    
    # ========== TEST 4: SWI (Conversioni) ==========
    print_header("TEST 4: SWI (Conversioni)")
    
    try:
        start_time = time.time()
        result = giornaliero_swi(client, target_date)
        elapsed = time.time() - start_time
        
        print(f"⏱️  Tempo esecuzione: {elapsed:.2f}s")
        
        if elapsed > 30:
            print(f"{Colors.YELLOW}⚠ WARNING{Colors.RESET} Timeout vicino (>30s)")
            results_summary['warnings'] += 1
        
        if validate_int_result(result, "SWI (Conversioni)"):
            results_summary['passed'] += 1
        else:
            results_summary['failed'] += 1
        
        swi = result
        total_swi = swi
        
    except Exception as e:
        print(f"{Colors.RED}✗ ERRORE{Colors.RESET} Estrazione fallita: {e}")
        results_summary['failed'] += 1
        return 1
    
    # ========== TEST 5: CR Commodity ==========
    print_header("TEST 5: Conversion Rate Commodity")
    
    try:
        start_time = time.time()
        result = calculate_cr(sessioni, swi)
        elapsed = time.time() - start_time
        
        print(f"⏱️  Tempo esecuzione: {elapsed:.2f}s")
        
        if validate_float_result(result, "CR Commodity"):
            results_summary['passed'] += 1
        else:
            results_summary['failed'] += 1
        
    except Exception as e:
        print(f"{Colors.RED}✗ ERRORE{Colors.RESET} Calcolo fallito: {e}")
        results_summary['failed'] += 1
    
    # ========== TEST 6: CR Luce&Gas ==========
    print_header("TEST 6: Conversion Rate Luce&Gas")
    
    try:
        start_time = time.time()
        result = calculate_cr(sessioni_lucegas, swi)
        elapsed = time.time() - start_time
        
        print(f"⏱️  Tempo esecuzione: {elapsed:.2f}s")
        
        if validate_float_result(result, "CR Luce&Gas"):
            results_summary['passed'] += 1
        else:
            results_summary['failed'] += 1
        
    except Exception as e:
        print(f"{Colors.RED}✗ ERRORE{Colors.RESET} Calcolo fallito: {e}")
        results_summary['failed'] += 1
    
    # ========== TEST 7: Start Funnel ==========
    print_header("TEST 7: Start Funnel")
    
    try:
        start_time = time.time()
        result = giornaliero_startfunnel(client, target_date)
        elapsed = time.time() - start_time
        
        print(f"⏱️  Tempo esecuzione: {elapsed:.2f}s")
        
        if elapsed > 30:
            print(f"{Colors.YELLOW}⚠ WARNING{Colors.RESET} Timeout vicino (>30s)")
            results_summary['warnings'] += 1
        
        print(f"\n{Colors.CYAN}📊 START FUNNEL{Colors.RESET}")
        if print_result("  Visualizzazioni Step 1", result, expected_type='int', required=True):
            results_summary['passed'] += 1
        else:
            results_summary['failed'] += 1
        
        start_funnel = result
        
    except Exception as e:
        print(f"{Colors.RED}✗ ERRORE{Colors.RESET} Estrazione fallita: {e}")
        results_summary['failed'] += 1
        start_funnel = 0
    
    # ========== TEST 8: CR Canalizzazione ==========
    print_header("TEST 8: CR Canalizzazione")
    
    try:
        start_time = time.time()
        result = giornaliero_cr_canalizzazione(total_swi, start_funnel)
        elapsed = time.time() - start_time
        
        print(f"⏱️  Tempo esecuzione: {elapsed:.2f}s")
        
        cr_value = validate_cr_canalizzazione(result)
        if cr_value is not None:
            results_summary['passed'] += 1
        else:
            results_summary['failed'] += 1
        
    except Exception as e:
        print(f"{Colors.RED}✗ ERRORE{Colors.RESET} Calcolo fallito: {e}")
        results_summary['failed'] += 1
    
    # ========== TEST 9: Prodotti ==========
    print_header("TEST 9: Performance Prodotti")
    
    try:
        start_time = time.time()
        result = giornaliero_prodotti(client, target_date, total_swi)
        elapsed = time.time() - start_time
        
        print(f"⏱️  Tempo esecuzione: {elapsed:.2f}s")
        
        if elapsed > 30:
            print(f"{Colors.YELLOW}⚠ WARNING{Colors.RESET} Timeout vicino (>30s)")
            results_summary['warnings'] += 1
        
        if validate_products(result, total_swi):
            results_summary['passed'] += 1
        else:
            results_summary['failed'] += 1
        
    except Exception as e:
        print(f"{Colors.RED}✗ ERRORE{Colors.RESET} Estrazione fallita: {e}")
        results_summary['failed'] += 1
    
    # ========== TEST 10: SWI per Commodity Type ==========
    print_header("TEST 10: SWI per Commodity Type")
    
    try:
        start_time = time.time()
        result = SWI_per_commodity_type(client, target_date)
        elapsed = time.time() - start_time
        
        print(f"⏱️  Tempo esecuzione: {elapsed:.2f}s")
        
        if elapsed > 30:
            print(f"{Colors.YELLOW}⚠ WARNING{Colors.RESET} Timeout vicino (>30s)")
            results_summary['warnings'] += 1
        
        if validate_commodity_type(result):
            results_summary['passed'] += 1
            
            # Verifica coerenza con SWI totale
            if 'Conversions' in result.columns:
                total_commodity = result['Conversions'].sum()
                diff = abs(total_commodity - total_swi)
                
                print(f"\n{Colors.CYAN}🔍 Verifica coerenza:{Colors.RESET}")
                print(f"  Totale SWI:           {total_swi}")
                print(f"  Somma commodity type: {int(total_commodity)}")
                print(f"  Differenza:           {int(diff)}")
                
                if diff > 10:  # Tolleranza
                    print(f"  {Colors.YELLOW}⚠ WARNING{Colors.RESET} Differenza significativa tra SWI totale e somma commodity types")
                    results_summary['warnings'] += 1
                else:
                    print(f"  {Colors.GREEN}✓ OK{Colors.RESET} Totali coerenti")
        else:
            results_summary['failed'] += 1
        
    except Exception as e:
        print(f"{Colors.RED}✗ ERRORE{Colors.RESET} Estrazione fallita: {e}")
        import traceback
        traceback.print_exc()
        results_summary['failed'] += 1
    
    # ========== RIEPILOGO FINALE ==========
    print_header("RIEPILOGO TEST")
    
    total = results_summary['passed'] + results_summary['failed']
    
    print(f"Test totali:     {total}")
    print(f"{Colors.GREEN}Test passati:    {results_summary['passed']}{Colors.RESET}")
    print(f"{Colors.RED}Test falliti:    {results_summary['failed']}{Colors.RESET}")
    print(f"{Colors.YELLOW}Warning:         {results_summary['warnings']}{Colors.RESET}")
    print()
    
    if results_summary['failed'] == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ TUTTE LE ESTRAZIONI VALIDE!{Colors.RESET}")
        print()
        print("Le estrazioni GA4 funzionano correttamente.")
        print("Puoi procedere con l'integrazione nel workflow principale.")
        print()
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ ALCUNE ESTRAZIONI HANNO FALLITO{Colors.RESET}")
        print()
        print("Verifica le query GA4 e riprova.")
        print()
        return 1


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description='Test estrazione GA4 con credenziali reali',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  # Test ieri (default)
  python test_ga4_extraction_real.py
  
  # Test data specifica
  python test_ga4_extraction_real.py --date 2025-11-02
        """
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Data da testare (YYYY-MM-DD), default = ieri'
    )
    
    args = parser.parse_args()
    
    try:
        return test_extraction(args.date)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️  Test interrotto dall'utente{Colors.RESET}\n")
        return 130
    except Exception as e:
        print(f"\n{Colors.RED}✗ ERRORE IMPREVISTO: {e}{Colors.RESET}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

