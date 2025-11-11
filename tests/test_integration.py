#!/usr/bin/env python3
"""
Script di test per verificare l'integrazione completa del sistema.

Questo script testa:
1. Caricamento configurazione
2. Importazione moduli
3. Presenza file necessari
4. Struttura directory
5. Validazione configurazione

NON richiede Redis attivo o API keys.
"""

import os
import sys
import yaml
import json
from pathlib import Path


class Colors:
    """ANSI color codes per output colorato."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_section(title: str):
    """Stampa un titolo di sezione."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def print_test(description: str, passed: bool, details: str = ""):
    """Stampa il risultato di un test."""
    status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if passed else f"{Colors.RED}✗ FAIL{Colors.RESET}"
    print(f"{status} - {description}")
    if details:
        print(f"     {Colors.YELLOW}{details}{Colors.RESET}")


def test_file_exists(filepath: str, description: str) -> bool:
    """Testa l'esistenza di un file."""
    exists = os.path.exists(filepath)
    print_test(description, exists, f"Path: {filepath}")
    return exists


def test_directory_exists(dirpath: str, description: str) -> bool:
    """Testa l'esistenza di una directory."""
    exists = os.path.isdir(dirpath)
    print_test(description, exists, f"Path: {dirpath}")
    return exists


def test_import(module_name: str, description: str) -> bool:
    """Testa l'importazione di un modulo."""
    try:
        __import__(module_name)
        print_test(description, True, f"Module: {module_name}")
        return True
    except ImportError as e:
        print_test(description, False, f"Error: {e}")
        return False


def main():
    """
    Esegue tutti i test di integrazione.
    """
    print(f"{Colors.BOLD}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║         TEST INTEGRAZIONE DAILY REPORT AGENT               ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")
    
    results = {
        'passed': 0,
        'failed': 0,
        'total': 0
    }
    
    def record_test(passed: bool):
        results['total'] += 1
        if passed:
            results['passed'] += 1
        else:
            results['failed'] += 1
        return passed
    
    # ========== TEST 1: File Principali ==========
    print_section("TEST 1: File Principali")
    
    record_test(test_file_exists("config.yaml", "Config file esiste"))
    record_test(test_file_exists("pyproject.toml", "pyproject.toml esiste"))
    record_test(test_file_exists("conversation_weborder.json", "Conversazione storica esiste"))
    record_test(test_file_exists("run_agent.py", "Script esecuzione esiste"))
    record_test(test_file_exists("approve_draft.py", "Script approvazione esiste"))
    
    # ========== TEST 2: Struttura Directory ==========
    print_section("TEST 2: Struttura Directory")
    
    record_test(test_directory_exists("agent", "Directory agent/"))
    record_test(test_directory_exists("ga4_extraction", "Directory ga4_extraction/"))
    record_test(test_directory_exists("output", "Directory output/"))
    record_test(test_directory_exists("email", "Directory email/"))
    record_test(test_directory_exists("email/archive", "Directory email/archive/"))
    
    # ========== TEST 3: File Moduli Agent ==========
    print_section("TEST 3: File Moduli Agent")
    
    record_test(test_file_exists("agent/agent.py", "agent.py esiste"))
    record_test(test_file_exists("agent/prompt.py", "prompt.py esiste"))
    record_test(test_file_exists("agent/tools.py", "tools.py esiste"))
    record_test(test_file_exists("agent/load_memory.py", "load_memory.py esiste"))
    
    # ========== TEST 4: Caricamento Configurazione ==========
    print_section("TEST 4: Validazione Configurazione")
    
    try:
        with open("config.yaml", 'r') as f:
            config = yaml.safe_load(f)
        
        # Verifica sezioni obbligatorie
        has_agent = 'agent' in config
        has_redis = 'redis' in config
        has_execution = 'execution' in config
        
        print_test("Sezione 'agent' presente", has_agent,
                   f"Model: {config.get('agent', {}).get('model', 'N/A')}")
        record_test(has_agent)
        
        print_test("Sezione 'redis' presente", has_redis,
                   f"Host: {config.get('redis', {}).get('host', 'N/A')}")
        record_test(has_redis)
        
        print_test("Sezione 'execution' presente", has_execution,
                   f"Output: {config.get('execution', {}).get('output_dir', 'N/A')}")
        record_test(has_execution)
        
    except Exception as e:
        print_test("Caricamento config.yaml", False, f"Error: {e}")
        record_test(False)
    
    # ========== TEST 5: Conversazione JSON ==========
    print_section("TEST 5: Validazione Conversazione")
    
    try:
        with open("conversation_weborder.json", 'r') as f:
            conv = json.load(f)
        
        has_name = 'name' in conv
        has_messages = 'chat_messages' in conv
        message_count = len(conv.get('chat_messages', []))
        correct_name = conv.get('name') == 'Weborder Residential Performance Update'
        
        test_name = has_name and correct_name
        print_test("Nome conversazione corretto", test_name,
                   f"Name: {conv.get('name', 'N/A')}")
        record_test(test_name)
        
        test_messages = has_messages and message_count > 0
        print_test("Messaggi presenti", test_messages,
                   f"Count: {message_count}")
        record_test(test_messages)
        
    except Exception as e:
        print_test("Caricamento conversation_weborder.json", False, f"Error: {e}")
        record_test(False)
    
    # ========== TEST 6: Importazione Moduli Python ==========
    print_section("TEST 6: Importazione Moduli Python")
    
    # Aggiungi directory corrente al path
    sys.path.insert(0, os.getcwd())
    
    record_test(test_import("yaml", "PyYAML installato"))
    record_test(test_import("redis", "Redis package installato"))
    record_test(test_import("pandas", "Pandas installato"))
    
    # Test import moduli custom (potrebbero fallire senza dipendenze)
    try:
        from agent import agent as agent_module
        print_test("Modulo agent importabile", True, "agent/agent.py")
        record_test(True)
    except Exception as e:
        print_test("Modulo agent importabile", False, f"Error: {str(e)[:50]}")
        record_test(False)
    
    try:
        from agent import prompt as prompt_module
        print_test("Modulo prompt importabile", True, "agent/prompt.py")
        record_test(True)
    except Exception as e:
        print_test("Modulo prompt importabile", False, f"Error: {str(e)[:50]}")
        record_test(False)
    
    try:
        from agent import load_memory as memory_module
        print_test("Modulo load_memory importabile", True, "agent/load_memory.py")
        record_test(True)
    except Exception as e:
        print_test("Modulo load_memory importabile", False, f"Error: {str(e)[:50]}")
        record_test(False)
    
    # ========== TEST 7: Dipendenze pyproject.toml ==========
    print_section("TEST 7: Dipendenze")
    
    try:
        with open("pyproject.toml", 'r') as f:
            content = f.read()
        
        required_deps = [
            "redis",
            "pyyaml",
            "python-dateutil",
            "datapizza-ai",
            "datapizza-ai-clients-anthropic"
        ]
        
        for dep in required_deps:
            has_dep = dep in content.lower()
            print_test(f"Dipendenza '{dep}' presente", has_dep)
            record_test(has_dep)
        
    except Exception as e:
        print_test("Lettura pyproject.toml", False, f"Error: {e}")
        record_test(False)
    
    # ========== RISULTATI FINALI ==========
    print_section("RISULTATI FINALI")
    
    total = results['total']
    passed = results['passed']
    failed = results['failed']
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"Totale test eseguiti: {total}")
    print(f"{Colors.GREEN}Test passati: {passed}{Colors.RESET}")
    print(f"{Colors.RED}Test falliti: {failed}{Colors.RESET}")
    print(f"Percentuale successo: {percentage:.1f}%")
    print()
    
    if failed == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ TUTTI I TEST SUPERATI!{Colors.RESET}")
        print()
        print("Il sistema è pronto per l'uso. Prossimi passi:")
        print("  1. Installa Redis: brew install redis")
        print("  2. Avvia Redis: redis-server &")
        print("  3. Carica memoria: python agent/load_memory.py")
        print("  4. Esegui agent: python run_agent.py")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ ALCUNI TEST SONO FALLITI{Colors.RESET}")
        print()
        print("Risolvi i problemi sopra indicati prima di procedere.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

