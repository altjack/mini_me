#!/usr/bin/env python3
"""
Script di test per verificare configurazione e connessione GA4
Esegui questo prima dello script principale per verificare che tutto funzioni
"""

import os
import sys
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Metric, RunReportRequest
)
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from dotenv import load_dotenv

load_dotenv()

PROPERTY_ID = os.getenv('PROPERTY_ID')
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']

def test_credentials():
    """Testa se credentials.json esiste"""
    print("1. Controllo credentials.json...")
    if os.path.exists('oath_credentials.json'):
        print("   ✓ credentials.json trovato")
        return True
    else:
        print("   ✗ credentials.json NON trovato!")
        print("   Scaricalo da Google Cloud Console")
        return False

def test_authentication():
    """Testa autenticazione OAuth"""
    print("\n2. Test autenticazione OAuth...")
    
    creds = None
    if os.path.exists('token.json'):
        print("   ℹ token.json esistente trovato")
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("   ℹ Refresh token in corso...")
            creds.refresh(Request())
        else:
            print("   ℹ Avvio flusso OAuth (si aprirà il browser)...")
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', 
                scopes=SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    print("   ✓ Autenticazione riuscita")
    return creds

def test_property_id():
    """Verifica Property ID"""
    print("\n3. Controllo Property ID...")
    if PROPERTY_ID == 'YOUR_PROPERTY_ID':
        print("   ✗ Property ID non configurato!")
        print("   Imposta GA4_PROPERTY_ID o modifica lo script")
        return False
    else:
        print(f"   ✓ Property ID: {PROPERTY_ID}")
        return True

def test_api_call(creds):
    """Test chiamata API reale"""
    print("\n4. Test chiamata API GA4...")
    
    try:
        client = BetaAnalyticsDataClient(credentials=creds)
        
        request = RunReportRequest(
            property=f'properties/{PROPERTY_ID}',
            metrics=[Metric(name='sessions')],
            date_ranges=[DateRange(start_date='yesterdat', end_date='yesterday')]
        )
        response = client.run_report(request)
        
        print(f"Response ricevuto: row_count={response.rows[0].metric_values[0].value}")

        if int(response.rows[0].metric_values[0].value) > 0:
            print("   ✓ API funzionante! Sessioni ultimi 30 giorni: {response.rows[0].metric_values[0].value}")
            return True
        else:
            print("   ✗ API non funzionante! Nessuna sessione trovata")
            return False
        
            
    except Exception as e:
        error_msg = str(e)
        print(f"   ✗ Errore chiamata API: {error_msg}")
        print("\n   Possibili cause:")
        
        if "API has not been used" in error_msg:
            print("   - Google Analytics Data API NON abilitata in Cloud Console")
            print("   → Vai su APIs & Services > Library > cerca 'Google Analytics Data API'")
        elif "PERMISSION_DENIED" in error_msg or "403" in error_msg:
            print("   - Account non ha accesso alla property GA4")
            print("   → Verifica in GA4 Admin > Property Access Management")
        elif "NOT_FOUND" in error_msg or "404" in error_msg:
            print("   - Property ID probabilmente errato")
            print("   → Verifica in GA4 Admin > Property Settings")
        else:
            print("   - Errore sconosciuto")
        
        print(f"\n   ℹ Per debug dettagliato, esegui: python3 debug_api.py")
        return False

def main():
    """Esegue tutti i test"""
    print("=" * 60)
    print("TEST CONFIGURAZIONE GA4 EXTRACTION")
    print("=" * 60)
    
    # Test 1: Credentials file
    if not test_credentials():
        return 1
    
    # Test 2: Authentication
    try:
        creds = test_authentication()
    except Exception as e:
        print(f"   ✗ Errore autenticazione: {e}")
        return 1
    
    # Test 3: Property ID
    if not test_property_id():
        return 1
    
    # Test 4: API call
    if not test_api_call(creds):
        return 1
    
    print("\n" + "=" * 60)
    print("✓ TUTTI I TEST SUPERATI!")
    print("=" * 60)
    print("\nPuoi ora eseguire lo script principale:")
    print("python3 ga4_extraction.py --period ieri")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())