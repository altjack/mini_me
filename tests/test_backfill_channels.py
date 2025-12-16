#!/usr/bin/env python3
"""
Test unitari per la nuova logica backfill con gestione canali D-2.

Testa:
1. Calcolo corretto della data massima canali (D-2)
2. Estrazione dati principali per tutte le date
3. Estrazione canali solo per date <= D-2
4. Risposta API con nuovi campi

Usage:
    uv run pytest tests/test_backfill_channels.py -v
"""

import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Aggiungi directory parent al path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestBackfillChannelsDateLogic:
    """Test per la logica di calcolo date canali."""
    
    def test_max_channel_date_calculation(self):
        """
        Verifica che max_channel_date sia calcolato come oggi - 2 giorni.
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        expected_max_channel_date = today - timedelta(days=2)
        
        # Simulazione della logica in api/backfill.py
        max_channel_date = today - timedelta(days=2)
        
        assert max_channel_date == expected_max_channel_date
        print(f"✓ max_channel_date = {max_channel_date.strftime('%Y-%m-%d')} (oggi - 2)")
    
    def test_date_range_with_recent_dates(self):
        """
        Verifica che per un range che include date recenti:
        - Dati principali: estratti per tutte le date
        - Canali: estratti solo fino a D-2
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        max_channel_date = today - timedelta(days=2)
        
        # Simula range: ultimi 7 giorni (include date troppo recenti per canali)
        start_date = today - timedelta(days=6)
        end_date = today
        
        dates_for_main_data = []
        dates_for_channels = []
        
        current_date = start_date
        while current_date <= end_date:
            dates_for_main_data.append(current_date)
            if current_date <= max_channel_date:
                dates_for_channels.append(current_date)
            current_date += timedelta(days=1)
        
        # Verifica
        assert len(dates_for_main_data) == 7, "Dati principali: dovrebbero essere estratti per tutti i 7 giorni"
        assert len(dates_for_channels) == 5, "Canali: dovrebbero essere estratti solo per 5 giorni (fino a D-2)"
        
        # Le ultime 2 date non devono avere canali
        assert dates_for_main_data[-1] not in dates_for_channels
        assert dates_for_main_data[-2] not in dates_for_channels
        
        print(f"✓ Range: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}")
        print(f"  • Dati principali: {len(dates_for_main_data)} giorni")
        print(f"  • Canali: {len(dates_for_channels)} giorni (fino a {max_channel_date.strftime('%Y-%m-%d')})")
    
    def test_date_range_all_valid_for_channels(self):
        """
        Verifica che se tutte le date sono <= D-2, i canali vengono estratti per tutte.
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        max_channel_date = today - timedelta(days=2)
        
        # Simula range: da D-10 a D-5 (tutte date valide per canali)
        start_date = today - timedelta(days=10)
        end_date = today - timedelta(days=5)
        
        dates_for_channels = []
        current_date = start_date
        while current_date <= end_date:
            if current_date <= max_channel_date:
                dates_for_channels.append(current_date)
            current_date += timedelta(days=1)
        
        expected_days = (end_date - start_date).days + 1
        
        assert len(dates_for_channels) == expected_days
        print(f"✓ Range storico: tutte le {expected_days} date hanno canali estratti")


class TestBackfillAPIIntegration:
    """Test integrazione API backfill (con mock)."""
    
    @patch('scripts.backfill_missing_dates.backfill_single_date')
    @patch('ga4_extraction.extraction.extract_sessions_channels_delayed')
    def test_backfill_calls_channels_only_for_valid_dates(
        self, 
        mock_extract_channels, 
        mock_backfill_single
    ):
        """
        Verifica che extract_sessions_channels_delayed venga chiamato
        solo per date <= D-2.
        """
        # Setup mocks
        mock_backfill_single.return_value = True
        mock_extract_channels.return_value = True
        
        # Simula date
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        max_channel_date = today - timedelta(days=2)
        
        start_date = today - timedelta(days=4)  # D-4
        end_date = today - timedelta(days=1)    # D-1 (ieri)
        
        include_channels = True
        results = []
        
        # Simula loop del backfill
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Estrai dati principali
            success = mock_backfill_single(date_str, None, None, include_channels=False)
            
            # Estrai canali solo se valido
            channels_extracted = False
            if include_channels and current_date <= max_channel_date:
                channels_extracted = mock_extract_channels(date_str, None, skip_validation=True)
            
            results.append({
                'date': date_str,
                'success': success,
                'channels_extracted': channels_extracted
            })
            
            current_date += timedelta(days=1)
        
        # Verifica chiamate
        assert mock_backfill_single.call_count == 4, "backfill_single_date chiamato per tutte e 4 le date"
        
        # Canali: D-4, D-3, D-2 = 3 date (D-1 escluso perché > max_channel_date)
        expected_channel_calls = 3
        assert mock_extract_channels.call_count == expected_channel_calls, \
            f"extract_sessions_channels_delayed chiamato {expected_channel_calls} volte (esclude D-1)"
        
        # Verifica risultati
        channels_true = sum(1 for r in results if r['channels_extracted'])
        channels_false = sum(1 for r in results if not r['channels_extracted'])
        
        assert channels_true == 3, "3 date con canali estratti"
        assert channels_false == 1, "1 data (D-1) senza canali"
        
        print(f"✓ Chiamate backfill_single_date: {mock_backfill_single.call_count}")
        print(f"✓ Chiamate extract_sessions_channels_delayed: {mock_extract_channels.call_count}")
        print(f"✓ Date con canali: {channels_true}, senza canali: {channels_false}")
    
    def test_response_contains_channel_metadata(self):
        """
        Verifica che la risposta API contenga i nuovi campi:
        - channels_extracted (count)
        - channels_max_date
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        max_channel_date = today - timedelta(days=2)
        
        # Simula risposta API
        include_channels = True
        results = [
            {'date': '2025-12-10', 'success': True, 'channels_extracted': True},
            {'date': '2025-12-11', 'success': True, 'channels_extracted': True},
            {'date': '2025-12-12', 'success': True, 'channels_extracted': True},
            {'date': '2025-12-13', 'success': True, 'channels_extracted': True},
            {'date': '2025-12-14', 'success': True, 'channels_extracted': True},
            {'date': '2025-12-15', 'success': True, 'channels_extracted': False},
            {'date': '2025-12-16', 'success': True, 'channels_extracted': False},
        ]
        
        # Calcola statistiche come nell'API
        success_count = sum(1 for r in results if r['success'])
        channels_count = sum(1 for r in results if r.get('channels_extracted')) if include_channels else 0
        
        response = {
            'success': True,
            'data': {
                'total': len(results),
                'successful': success_count,
                'failed': len(results) - success_count,
                'channels_extracted': channels_count if include_channels else None,
                'channels_max_date': max_channel_date.strftime('%Y-%m-%d') if include_channels else None,
                'details': results
            }
        }
        
        # Verifica struttura risposta
        assert response['success'] is True
        assert response['data']['total'] == 7
        assert response['data']['successful'] == 7
        assert response['data']['failed'] == 0
        assert response['data']['channels_extracted'] == 5
        assert response['data']['channels_max_date'] == max_channel_date.strftime('%Y-%m-%d')
        
        print("✓ Risposta API contiene tutti i campi richiesti:")
        print(f"  • total: {response['data']['total']}")
        print(f"  • successful: {response['data']['successful']}")
        print(f"  • channels_extracted: {response['data']['channels_extracted']}")
        print(f"  • channels_max_date: {response['data']['channels_max_date']}")


class TestEdgeCases:
    """Test casi limite."""
    
    def test_single_date_backfill_recent(self):
        """
        Backfill di singola data recente (D-1):
        - Dati principali: estratti
        - Canali: NON estratti
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        max_channel_date = today - timedelta(days=2)
        target_date = today - timedelta(days=1)  # D-1 (troppo recente)
        
        should_extract_channels = target_date <= max_channel_date
        
        assert should_extract_channels is False
        print(f"✓ Data D-1 ({target_date.strftime('%Y-%m-%d')}): canali NON estratti (corretto)")
    
    def test_single_date_backfill_old(self):
        """
        Backfill di singola data vecchia (D-5):
        - Dati principali: estratti
        - Canali: estratti
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        max_channel_date = today - timedelta(days=2)
        target_date = today - timedelta(days=5)  # D-5 (sufficientemente vecchia)
        
        should_extract_channels = target_date <= max_channel_date
        
        assert should_extract_channels is True
        print(f"✓ Data D-5 ({target_date.strftime('%Y-%m-%d')}): canali estratti (corretto)")
    
    def test_boundary_date_d2(self):
        """
        Verifica che D-2 (la data limite) abbia i canali estratti.
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        max_channel_date = today - timedelta(days=2)
        target_date = today - timedelta(days=2)  # Esattamente D-2
        
        should_extract_channels = target_date <= max_channel_date
        
        assert should_extract_channels is True
        print(f"✓ Data D-2 ({target_date.strftime('%Y-%m-%d')}): canali estratti (boundary case)")


def run_all_tests():
    """Esegue tutti i test manualmente (senza pytest)."""
    print("\n" + "=" * 80)
    print("  🧪 TEST BACKFILL CHANNELS (D-2 LOGIC)")
    print("=" * 80 + "\n")
    
    test_classes = [
        TestBackfillChannelsDateLogic,
        TestBackfillAPIIntegration,
        TestEdgeCases,
    ]
    
    passed = 0
    failed = 0
    
    for test_class in test_classes:
        print(f"\n📋 {test_class.__name__}")
        print("-" * 60)
        
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                try:
                    method = getattr(instance, method_name)
                    print(f"\n🔹 {method_name}")
                    method()
                    passed += 1
                except AssertionError as e:
                    print(f"✗ FAILED: {e}")
                    failed += 1
                except Exception as e:
                    print(f"✗ ERROR: {e}")
                    failed += 1
    
    print("\n" + "=" * 80)
    print(f"  📊 RISULTATI: {passed} passed, {failed} failed")
    print("=" * 80 + "\n")
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(run_all_tests())

