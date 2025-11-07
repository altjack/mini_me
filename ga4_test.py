#!/usr/bin/env python3
"""
Script di test per verificare configurazione e connessione GA4
Test specifico per session_lucegas_filter
"""

import os
import sys
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Metric, RunReportRequest, FilterExpression, Filter
)
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv
from datetime import datetime, timedelta

from typing import Dict
from ga4_extraction import session_lucegas_filter

load_dotenv()

PROPERTY_ID = os.getenv('PROPERTY_ID')
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']



def get_credentials() -> Credentials:
    """Gestisce autenticazione OAuth"""
    creds = None

    if os.path.exists('credentials/token.json'):
        creds = Credentials.from_authorized_user_file('credentials/token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refresh token in corso...")
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials/credentials.json'):
                print("✗ File credentials/credentials.json non trovato!")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials/credentials.json',
                scopes=SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open('credentials/token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

def calculate_dates(period_type: str = 'ieri') -> Dict[str, str]:
    """
    Calcola le date per i due periodi di confronto
    
    Args:
        period_type: 'ieri' o 'weekend'
    
    Returns:
        Dict con date_from1, date_to1, date_from2, date_to2
    """
    today = datetime.now()
    
    if period_type == 'ieri':
        # Periodo 1: ieri
        date_to1 = today - timedelta(days=1)
        date_from1 = date_to1
        
        # Periodo 2: 7 giorni prima
        date_to2 = date_to1 - timedelta(days=7)
        date_from2 = date_to2
        
    else:
        raise ValueError(f"period_type non valido: {period_type}")
    
    return {
        'date_from1': date_from1.strftime('%Y-%m-%d'),
        'date_to1': date_to1.strftime('%Y-%m-%d'),
        'date_from2': date_from2.strftime('%Y-%m-%d'),
        'date_to2': date_to2.strftime('%Y-%m-%d')
    }

def test_session_commodity_filter(creds):
    """
    Test specifico per session_commodity_filter
    Verifica che il filtro funzioni correttamente
    """
    print("\n" + "="*80)
    print("TEST SESSION_COMMODITY_FILTER")
    print("="*80)
    
    try:
        client = BetaAnalyticsDataClient(credentials=creds)
        dates = calculate_dates('ieri')
        request = RunReportRequest(
            property=f'properties/{PROPERTY_ID}',
            metrics=[Metric(name='sessions')],
            date_ranges=[
                DateRange(
                    start_date=dates['date_from1'],
                    end_date=dates['date_to1']
                ),
                DateRange(
                    start_date=dates['date_from2'],
                    end_date=dates['date_to2']
                )
            ],
            dimension_filter=session_commodity_filter()
        )
        print("\n--- Request inviata ---")
        print(f"Property: {PROPERTY_ID}")
        print(f"Metrics: sessions")
        print(f"Date range 1: {dates['date_from1']} -> {dates['date_to1']}")
        print(f"Date range 2: {dates['date_from2']} -> {dates['date_to2']}")
        print(f"Filtro applicato: session_commodity_filter() - pageLocation CONTAINS '/offerta/casa/gas-e-luce' AND NOT fullPageUrl BEGINS_WITH 'pp.'")
        print("="*80)

        response = client.run_report(request)
        print("\n--- Response completa (raw) ---")
        print(response)
        print("\n" + "="*80)
        return True

    except Exception as e:
        print(f"\n✗ ERRORE durante il test:")
        print(f"  {type(e).__name__}: {e}")
        print("\nDettagli completi dell'errore:")
        import traceback
        traceback.print_exc()
        return False

def test_session_lucegas_filter(creds):
    """
    Test specifico per session_lucegas_filter
    Verifica che il filtro funzioni correttamente
    """
    print("\n" + "="*80)
    print("TEST SESSION_LUCEGAS_FILTER")
    print("="*80)

    try:
        client = BetaAnalyticsDataClient(credentials=creds)

        # Calcola le date
        dates = calculate_dates('ieri')

        # Request con filtro
        request = RunReportRequest(
            property=f'properties/{PROPERTY_ID}',
            metrics=[Metric(name='sessions')],
            date_ranges=[
            DateRange(
                start_date=dates['date_from1'],
                end_date=dates['date_to1']
            ),
            DateRange(
                start_date=dates['date_from2'],
                end_date=dates['date_to2']
            )
        ],
            dimension_filter=session_lucegas_filter()
        )

        print("\n--- Request inviata ---")
        print(f"Property: {PROPERTY_ID}")
        print(f"Metrics: sessions")
        print(f"Date range 1: {dates['date_from1']} -> {dates['date_to1']}")
        print(f"Date range 2: {dates['date_from2']} -> {dates['date_to2']}")
        print(f"Filtro applicato: session_lucegas_filter() - pageLocation CONTAINS '/offerta/casa/gas-e-luce' AND NOT fullPageUrl BEGINS_WITH 'pp.'")
        print("="*80)

        response = client.run_report(request)

        print("\n--- Response completa (raw) ---")
        print(response)
        print("\n" + "="*80)

        return True

    except Exception as e:
        print(f"\n✗ ERRORE durante il test:")
        print(f"  {type(e).__name__}: {e}")
        print("\nDettagli completi dell'errore:")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Esegue il test del filtro session_lucegas"""
    print("=" * 80)
    print("TEST SESSION_LUCEGAS_FILTER - GA4 EXTRACTION")
    print("=" * 80)

    # Verifica Property ID
    if not PROPERTY_ID or PROPERTY_ID == 'YOUR_PROPERTY_ID':
        print("✗ Property ID non configurato!")
        print("  Imposta PROPERTY_ID nel file .env")
        return 1

    print(f"\nProperty ID: {PROPERTY_ID}")

    # Autenticazione
    try:
        print("\nAutenticazione in corso...")
        creds = get_credentials()
        print("✓ Autenticazione completata")
    except Exception as e:
        print(f"✗ Errore autenticazione: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Test filtro
    if not test_session_lucegas_filter(creds):
        print("\n✗ TEST FALLITO")
        return 1

    print("\n" + "=" * 80)
    print("✓ TEST COMPLETATO CON SUCCESSO!")
    print("=" * 80)

    return 0

if __name__ == '__main__':
    sys.exit(main())

