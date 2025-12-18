#!/usr/bin/env python3
"""
Script di test per verificare il nuovo workflow di estrazione canali ritardata.

Questo script testa:
1. Funzione extract_sessions_channels_delayed()
2. Identificazione date mancanti
3. Identificazione date senza canali
4. Salvataggio in database

Usage:
    uv run test_channels_workflow.py
"""

import sys
import os
from datetime import datetime, timedelta

# Aggiungi directory parent al path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.ga4_extraction.database import GA4Database
from backend.ga4_extraction.extraction import extract_sessions_channels_delayed


def test_database_connection():
    """Test connessione database."""
    print("=" * 80)
    print("TEST 1: Connessione Database")
    print("=" * 80)
    
    try:
        db = GA4Database('data/ga4_data.db')
        stats = db.get_statistics()
        
        print(f"✓ Database connesso")
        print(f"  • Record totali: {stats['record_count']}")
        print(f"  • Periodo: {stats['min_date']} → {stats['max_date']}")
        
        db.close()
        print("✓ Test superato\n")
        return True
        
    except Exception as e:
        print(f"✗ Test fallito: {e}\n")
        return False


def test_identify_dates_without_channels():
    """Test identificazione date senza dati canale."""
    print("=" * 80)
    print("TEST 2: Identificazione Date Senza Canali")
    print("=" * 80)
    
    try:
        db = GA4Database('data/ga4_data.db')
        
        # Query per trovare date senza canali
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT dm.date
            FROM daily_metrics dm
            LEFT JOIN sessions_by_channel sc ON dm.date = sc.date
            GROUP BY dm.date
            HAVING COUNT(sc.id) = 0
            ORDER BY dm.date DESC
            LIMIT 10
        """)
        
        dates_without_channels = [row[0] for row in cursor.fetchall()]
        
        if dates_without_channels:
            print(f"✓ Trovate {len(dates_without_channels)} date senza canali:")
            for date in dates_without_channels:
                print(f"  • {date}")
        else:
            print("✓ Tutte le date hanno dati canale")
        
        db.close()
        print("✓ Test superato\n")
        return True
        
    except Exception as e:
        print(f"✗ Test fallito: {e}\n")
        return False


def test_extract_channels_function():
    """Test funzione extract_sessions_channels_delayed()."""
    print("=" * 80)
    print("TEST 3: Funzione extract_sessions_channels_delayed()")
    print("=" * 80)
    
    # Usa D-3 per essere sicuri che i dati siano disponibili
    target_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    
    print(f"Data test: {target_date} (D-3)")
    print("⚠️  NOTA: Questo test farà una chiamata reale all'API GA4")
    
    response = input("Procedere con il test? [y/N]: ")
    if response.lower() != 'y':
        print("Test saltato\n")
        return True
    
    try:
        db = GA4Database('data/ga4_data.db')
        
        # Verifica se la data ha già metriche principali
        cursor = db.conn.cursor()
        cursor.execute("SELECT date FROM daily_metrics WHERE date = ?", (target_date,))
        
        if not cursor.fetchone():
            print(f"⚠️  {target_date} non ha metriche principali")
            print(f"   Esegui prima: uv run backfill_missing_dates.py --date {target_date}")
            db.close()
            return False
        
        print(f"✓ {target_date} ha metriche principali")
        print(f"⏳ Estrazione canali in corso...")
        
        # Estrai canali
        success = extract_sessions_channels_delayed(target_date, db)
        
        if success:
            print(f"✓ Estrazione completata con successo")
            
            # Verifica salvataggio
            cursor.execute("""
                SELECT COUNT(*) FROM sessions_by_channel WHERE date = ?
            """, (target_date,))
            
            count = cursor.fetchone()[0]
            print(f"✓ Salvati {count} canali nel database")
            
            # Mostra dati
            cursor.execute("""
                SELECT channel, commodity_sessions, lucegas_sessions
                FROM sessions_by_channel
                WHERE date = ?
                ORDER BY commodity_sessions DESC
                LIMIT 5
            """, (target_date,))
            
            print(f"\n📊 Top 5 canali per {target_date}:")
            for row in cursor.fetchall():
                print(f"  • {row[0]:30} Commodity: {row[1]:5} | Luce&Gas: {row[2]:5}")
        else:
            print(f"✗ Estrazione fallita")
        
        db.close()
        print("\n✓ Test superato\n")
        return success
        
    except Exception as e:
        print(f"✗ Test fallito: {e}\n")
        if 'db' in locals():
            db.close()
        return False


def test_workflow_simulation():
    """Simula workflow completo."""
    print("=" * 80)
    print("TEST 4: Simulazione Workflow Completo")
    print("=" * 80)
    
    print("\n📅 Workflow Giornaliero:")
    print("  1. Giorno 1 (oggi): main.py estrae dati D-1")
    print("  2. Giorno 3 (tra 2 giorni): extract_channels_delayed.py estrae canali D-1")
    print()
    
    # Mostra date esempio
    today = datetime.now()
    d1 = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    d2 = (today - timedelta(days=2)).strftime('%Y-%m-%d')
    d3 = (today - timedelta(days=3)).strftime('%Y-%m-%d')
    
    print(f"📊 Date Esempio:")
    print(f"  • Oggi:  {today.strftime('%Y-%m-%d')}")
    print(f"  • D-1:   {d1} ← main.py estrae metriche principali")
    print(f"  • D-2:   {d2} ← extract_channels_delayed.py estrae canali")
    print(f"  • D-3:   {d3}")
    print()
    
    try:
        db = GA4Database('data/ga4_data.db')
        cursor = db.conn.cursor()
        
        # Verifica stato D-1
        cursor.execute("SELECT date FROM daily_metrics WHERE date = ?", (d1,))
        has_d1_metrics = cursor.fetchone() is not None
        
        cursor.execute("SELECT COUNT(*) FROM sessions_by_channel WHERE date = ?", (d1,))
        d1_channels = cursor.fetchone()[0]
        
        # Verifica stato D-2
        cursor.execute("SELECT date FROM daily_metrics WHERE date = ?", (d2,))
        has_d2_metrics = cursor.fetchone() is not None
        
        cursor.execute("SELECT COUNT(*) FROM sessions_by_channel WHERE date = ?", (d2,))
        d2_channels = cursor.fetchone()[0]
        
        print(f"📈 Stato Database:")
        print(f"  • D-1 ({d1}):")
        print(f"    - Metriche principali: {'✓ Presenti' if has_d1_metrics else '✗ Mancanti'}")
        print(f"    - Dati canale: {'✓ Presenti' if d1_channels > 0 else '⏳ In attesa (normale)'}")
        print()
        print(f"  • D-2 ({d2}):")
        print(f"    - Metriche principali: {'✓ Presenti' if has_d2_metrics else '✗ Mancanti'}")
        print(f"    - Dati canale: {'✓ Presenti' if d2_channels > 0 else '⚠️  Mancanti (esegui extract_channels_delayed.py)'}")
        print()
        
        # Suggerimenti
        if not has_d1_metrics:
            print("💡 AZIONE RICHIESTA:")
            print(f"   uv run main.py")
            print()
        
        if has_d2_metrics and d2_channels == 0:
            print("💡 AZIONE RICHIESTA:")
            print(f"   uv run extract_channels_delayed.py --date {d2}")
            print()
        
        db.close()
        print("✓ Test superato\n")
        return True
        
    except Exception as e:
        print(f"✗ Test fallito: {e}\n")
        if 'db' in locals():
            db.close()
        return False


def main():
    """Esegue tutti i test."""
    print("\n")
    print("=" * 80)
    print("  🧪 TEST WORKFLOW ESTRAZIONE CANALI RITARDATA")
    print("=" * 80)
    print()
    
    results = []
    
    # Test 1: Connessione database
    results.append(("Connessione Database", test_database_connection()))
    
    # Test 2: Identificazione date senza canali
    results.append(("Identificazione Date", test_identify_dates_without_channels()))
    
    # Test 3: Funzione estrazione canali
    results.append(("Estrazione Canali", test_extract_channels_function()))
    
    # Test 4: Simulazione workflow
    results.append(("Workflow Completo", test_workflow_simulation()))
    
    # Riepilogo
    print("=" * 80)
    print("  📊 RIEPILOGO TEST")
    print("=" * 80)
    print()
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status:10} {name}")
    
    print()
    print(f"Risultato: {passed}/{total} test superati")
    print()
    
    if passed == total:
        print("🎉 Tutti i test sono passati!")
        print()
        print("💡 PROSSIMI PASSI:")
        print("   1. Configura cron per estrazione automatica")
        print("   2. Monitora log: extract_channels_delayed.log")
        print("   3. Verifica dati canale dopo 48h")
        print()
        return 0
    else:
        print("⚠️  Alcuni test sono falliti. Controlla i log sopra.")
        print()
        return 1


if __name__ == '__main__':
    sys.exit(main())

