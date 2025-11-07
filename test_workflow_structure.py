#!/usr/bin/env python3
"""
Script di test per verificare la struttura del workflow.
Non esegue l'intero workflow, ma verifica che:
1. Tutti i moduli possano essere importati
2. Le funzioni workflow esistano e abbiano le signature corrette
3. La configurazione sia valida
"""

import sys
import os

# Aggiungi directory corrente al path
sys.path.append(os.path.dirname(__file__))

def test_imports():
    """Test che tutti i moduli possano essere importati."""
    print("🔍 Test 1: Verifica imports...")
    
    try:
        from run_agent import run_agent_workflow, setup_logging, load_config, ensure_directories
        print("   ✓ run_agent importato correttamente")
    except Exception as e:
        print(f"   ❌ Errore import run_agent: {e}")
        return False
    
    try:
        from approve_draft import approve_draft_workflow, show_memory_stats
        print("   ✓ approve_draft importato correttamente")
    except Exception as e:
        print(f"   ❌ Errore import approve_draft: {e}")
        return False
    
    try:
        import yaml
        print("   ✓ yaml disponibile")
    except Exception as e:
        print(f"   ❌ Errore import yaml: {e}")
        return False
    
    return True


def test_config():
    """Test che la configurazione sia valida."""
    print("\n🔍 Test 2: Verifica configurazione...")
    
    try:
        from run_agent import load_config
        config = load_config()
        print("   ✓ config.yaml caricato correttamente")
        
        # Verifica chiavi essenziali
        required_keys = ['agent', 'execution', 'redis']
        for key in required_keys:
            if key not in config:
                print(f"   ❌ Chiave mancante in config: {key}")
                return False
            print(f"   ✓ Chiave '{key}' presente")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Errore caricamento config: {e}")
        return False


def test_functions_signatures():
    """Test che le funzioni workflow abbiano le signature corrette."""
    print("\n🔍 Test 3: Verifica signature funzioni...")
    
    try:
        from run_agent import run_agent_workflow
        from approve_draft import approve_draft_workflow
        import inspect
        
        # Verifica run_agent_workflow
        sig = inspect.signature(run_agent_workflow)
        params = list(sig.parameters.keys())
        if 'config' not in params:
            print("   ❌ run_agent_workflow: parametro 'config' mancante")
            return False
        print("   ✓ run_agent_workflow ha signature corretta")
        
        # Verifica approve_draft_workflow
        sig = inspect.signature(approve_draft_workflow)
        params = list(sig.parameters.keys())
        if 'config' not in params:
            print("   ❌ approve_draft_workflow: parametro 'config' mancante")
            return False
        print("   ✓ approve_draft_workflow ha signature corretta")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Errore verifica signature: {e}")
        return False


def test_directories():
    """Test che le directory necessarie esistano o possano essere create."""
    print("\n🔍 Test 4: Verifica directory...")
    
    try:
        from run_agent import load_config, ensure_directories
        config = load_config()
        ensure_directories(config)
        
        output_dir = config['execution']['output_dir']
        archive_dir = config['execution']['archive_dir']
        
        if os.path.exists(output_dir):
            print(f"   ✓ Directory output esiste: {output_dir}")
        else:
            print(f"   ❌ Directory output non esiste: {output_dir}")
            return False
        
        if os.path.exists(archive_dir):
            print(f"   ✓ Directory archive esiste: {archive_dir}")
        else:
            print(f"   ❌ Directory archive non esiste: {archive_dir}")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Errore verifica directory: {e}")
        return False


def test_ga4_module():
    """Test che il modulo GA4 possa essere importato."""
    print("\n🔍 Test 5: Verifica modulo GA4...")
    
    try:
        # Cambia directory per import relativi
        original_dir = os.getcwd()
        ga4_dir = os.path.join(os.path.dirname(__file__), 'ga4_extraction')
        os.chdir(ga4_dir)
        
        # Prova import
        from main import main as ga4_main
        print("   ✓ Modulo ga4_extraction.main importato correttamente")
        
        # Ritorna alla directory originale
        os.chdir(original_dir)
        
        return True
        
    except Exception as e:
        print(f"   ❌ Errore import ga4_extraction.main: {e}")
        # Ritorna alla directory originale
        try:
            os.chdir(original_dir)
        except:
            pass
        return False


def main():
    """Esegue tutti i test."""
    print("=" * 70)
    print("  🧪 TEST STRUTTURA WORKFLOW")
    print("=" * 70)
    print()
    
    tests = [
        test_imports,
        test_config,
        test_functions_signatures,
        test_directories,
        test_ga4_module,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test fallito con eccezione: {e}")
            results.append(False)
    
    # Riepilogo
    print("\n" + "=" * 70)
    print("  📊 RIEPILOGO TEST")
    print("=" * 70)
    print()
    
    passed = sum(results)
    total = len(results)
    
    print(f"Test passati: {passed}/{total}")
    print()
    
    if all(results):
        print("✅ Tutti i test sono passati!")
        print("\n🚀 Il workflow è pronto per essere eseguito con: uv run main.py")
        return 0
    else:
        print("❌ Alcuni test sono falliti")
        print("\n⚠️  Risolvi gli errori prima di eseguire il workflow")
        return 1


if __name__ == "__main__":
    sys.exit(main())

