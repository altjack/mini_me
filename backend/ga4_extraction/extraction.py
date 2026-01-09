#!/usr/bin/env python3
"""
Migrazione da Google Apps Script a Python per estrazione dati GA4
Traduce tutte le funzioni dello script originale

Features:
- Rate limiting per rispettare limiti GA4 API (10 rps)
- Retry automatico con exponential backoff su errori transitori
- Logging strutturato
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, RunReportRequest,
    FilterExpression, Filter, FilterExpressionList
)
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from .filters import session_commodity_filter, session_lucegas_filter, funnel_weborder_step1_filter, commodity_type_filter
from .config import get_credentials
from .rate_limiter import get_rate_limiter
from .retry import ga4_retry

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# Imposta questi valori con i tuoi dati
PROPERTY_ID = "281687433"
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']

# Configurazione logging - usa /tmp su Vercel/Lambda (filesystem read-only)
_is_serverless = os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME') or __file__.startswith('/var/task')
LOG_PATH = '/tmp/ga4_extraction.log' if _is_serverless else 'ga4_extraction.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# AUTENTICAZIONE OAUTH (lazy)
# ============================================================================

_ga_client = None


def get_ga_client() -> BetaAnalyticsDataClient:
    """
    Restituisce un client GA4 con inizializzazione lazy.
    Evita eccezioni a import time in ambienti serverless.
    """
    global _ga_client
    if _ga_client is None:
        creds = get_credentials()
        if not creds:
            raise Exception("GA4 credentials not configured (GOOGLE_CREDENTIALS_JSON missing or invalid)")
        _ga_client = BetaAnalyticsDataClient(credentials=creds)
    return _ga_client


@ga4_retry()
def _execute_ga4_request(client: BetaAnalyticsDataClient, request: RunReportRequest):
    """
    Esegue una richiesta GA4 con rate limiting e retry automatico.

    Questa funzione wrappa tutte le chiamate a client.run_report() per:
    - Rispettare il rate limit GA4 (10 rps)
    - Retry automatico su errori transitori (503, 429, timeout)
    - Logging delle performance

    Args:
        client: Client GA4 BetaAnalyticsDataClient
        request: RunReportRequest da eseguire

    Returns:
        Response dalla GA4 API
    """
    # Applica rate limiting prima della chiamata
    rate_limiter = get_rate_limiter()
    wait_time = rate_limiter.wait_if_needed()

    if wait_time > 0:
        logger.debug(f"Rate limited: atteso {wait_time:.3f}s")

    # Esegui la richiesta (il retry è gestito dal decorator @ga4_retry)
    return client.run_report(request)


# ============================================================================
# FUNZIONI PER GESTIONE DATE
# ============================================================================

def calculate_dates(period_type: str = 'ieri') -> Dict[str, str]:
    """
    Calcola le date per il periodo di estrazione
    
    Args:
        period_type: 'ieri' o 'weekend'
    
    Returns:
        Dict con date_from e date_to
    """
    today = datetime.now()
    
    if period_type == 'ieri':
        # Periodo: ieri
        date_to = today - timedelta(days=1)
        date_from = date_to
        
    else:
        raise ValueError(f"period_type non valido: {period_type}")
    
    return {
        'date_from': date_from.strftime('%Y-%m-%d'),
        'date_to': date_to.strftime('%Y-%m-%d')
    }

# ============================================================================
# FUNZIONE 1: SESSIONI
# ============================================================================

def sessions(
    client: BetaAnalyticsDataClient,
    date: str,
    filter_expression=None
) -> int:
    """
    Estrae il numero di sessioni per una data specifica.
    
    Args:
        client: Client GA4 BetaAnalyticsDataClient
        date: Data in formato YYYY-MM-DD
        filter_expression: Filtro opzionale (es. session_commodity_filter() o session_lucegas_filter())
                          Se None, estrae tutte le sessioni senza filtro
    
    Returns:
        Numero di sessioni (int)
    """
    # Determina label per output
    if filter_expression is None:
        label = "SESSIONI TOTALI"
    elif 'commodity' in str(filter_expression).lower():
        label = "SESSIONI COMMODITY"
    elif 'lucegas' in str(filter_expression).lower() or 'luce' in str(filter_expression).lower():
        label = "SESSIONI LUCE&GAS"
    else:
        label = "SESSIONI"
    
    request = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        metrics=[Metric(name='sessions')],
        date_ranges=[DateRange(start_date=date, end_date=date)],
        dimension_filter=filter_expression if filter_expression else None
    )

    response = _execute_ga4_request(client, request)

    # Processa la response per estrarre il valore
    sessions_count = 0

    # Prova prima con totals
    if response.totals and len(response.totals) > 0:
        sessions_count = int(response.totals[0].metric_values[0].value)
    # Altrimenti usa rows
    elif response.rows and len(response.rows) > 0:
        sessions_count = int(response.rows[0].metric_values[0].value)
    else:
        logger.warning(f"Nessun dato per sessioni ({label})")
        return 0

    # Output pulito
    print("\n" + "="*80)
    print(label)
    print("="*80)
    print(f"Date: {date}")
    print(f"Sessioni: {sessions_count}")
    print("="*80 + "\n")

    return sessions_count

# ============================================================================
# FUNZIONE 2: SWI (CONVERSIONI)
# ============================================================================

def giornaliero_swi(client: BetaAnalyticsDataClient, date: str) -> int:
    """
    Estrae conversioni weborder_residenziale per una data specifica.
    Equivalente a giornaliero_SWI() in Apps Script
    
    Args:
        client: Client GA4 BetaAnalyticsDataClient
        date: Data in formato YYYY-MM-DD
    
    Returns:
        Numero di conversioni (int)
    """
    request = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        metrics=[Metric(name='keyEvents:weborder_residenziale')],
        date_ranges=[DateRange(start_date=date, end_date=date)]
    )

    response = _execute_ga4_request(client, request)

    # Processa la response per estrarre il valore
    conversions = 0
    
    # Prova prima con totals
    if response.totals and len(response.totals) > 0:
        conversions = int(response.totals[0].metric_values[0].value)
    # Altrimenti usa rows
    elif response.rows and len(response.rows) > 0:
        conversions = int(response.rows[0].metric_values[0].value)
    else:
        logger.warning("Nessun dato per conversioni SWI")
        return 0

    # Output pulito
    print("\n" + "="*80)
    print("SWI (CONVERSIONI)")
    print("="*80)
    print(f"Date: {date}")
    print(f"Conversioni: {conversions}")
    print("="*80 + "\n")

    return conversions

# ============================================================================
# FUNZIONE 3: CONVERSION RATE CALCULATOR
# ============================================================================

def calculate_cr(sessioni: int, conversioni: int) -> float:
    """
    Calcola conversion rate (percentuale).
    
    Args:
        sessioni: Numero di sessioni
        conversioni: Numero di conversioni
    
    Returns:
        Conversion rate in percentuale (float)
    """
    if sessioni > 0:
        cr = (conversioni / sessioni) * 100
    else:
        cr = 0.0
    
    return cr

# ============================================================================
# FUNZIONE 4: PRODOTTI
# ============================================================================

def giornaliero_prodotti(
    client: BetaAnalyticsDataClient,
    date: str,
    total_swi: float
) -> pd.DataFrame:
    """
    Raggruppa conversioni per prodotto (fixa, trend, pernoi, altri)
    Equivalente a giornaliero_prodotti() in Apps Script
    """
    logger.info("Esecuzione: giornaliero_prodotti")

    request = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        dimensions=[Dimension(name='customEvent:prodotto')],
        metrics=[Metric(name='keyEvents:weborder_residenziale')],
        date_ranges=[DateRange(start_date=date, end_date=date)]
    )

    response = _execute_ga4_request(client, request)

    if not response.rows:
        logger.warning("Nessun dato restituito per prodotti")
        return pd.DataFrame()

    # Raggruppa per categoria
    grouped = {
        'fixa': 0.0,
        'trend': 0.0,
        'pernoi': 0.0,
        'sempre': 0.0
    }
    others = {}

    for row in response.rows:
        prodotto = row.dimension_values[0].value.lower()
        valore = float(row.metric_values[0].value)

        if 'fixa' in prodotto:
            grouped['fixa'] += valore
        elif 'trend' in prodotto:
            grouped['trend'] += valore
        elif 'pernoi' in prodotto:
            grouped['pernoi'] += valore
        elif 'sempre' in prodotto:
            grouped['sempre'] += valore
        else:
            if prodotto in others:
                others[prodotto] += valore
            else:
                others[prodotto] = valore

    # Crea DataFrame risultato
    results = []
    for product, total in grouped.items():
        percentage = (total / total_swi * 100) if total_swi > 0 else 0
        results.append({
            'Product': product,
            'Total': total,
            'Percentage': f"{percentage:.2f}%"
        })

    for product, total in others.items():
        percentage = (total / total_swi * 100) if total_swi > 0 else 0
        results.append({
            'Product': product,
            'Total': total,
            'Percentage': f"{percentage:.2f}%"
        })

    result_df = pd.DataFrame(results)
    logger.info(f"Prodotti analizzati: {len(result_df)}")
    
    # Output pulito
    print("\n" + "="*80)
    print("PRODOTTI")
    print("="*80)
    print(f"Date: {date}")
    print(f"\nProdotti principali:")
    for product, total in grouped.items():
        if total > 0:  # Mostra solo prodotti con valore > 0
            percentage = (total / total_swi * 100) if total_swi > 0 else 0
            print(f"  {product.capitalize():15} {int(total):5} conversioni ({percentage:.2f}%)")
    
    if others:
        print(f"\nAltri prodotti:")
        for product, total in others.items():
            percentage = (total / total_swi * 100) if total_swi > 0 else 0
            print(f"  {product:15} {int(total):5} conversioni ({percentage:.2f}%)")
    
    print("="*80 + "\n")
    
    return result_df

# ============================================================================
# FUNZIONE 5: START FUNNEL
# ============================================================================

def giornaliero_startfunnel(
    client: BetaAnalyticsDataClient,
    date: str
) -> float:
    """
    Conta visualizzazioni del primo step del funnel
    Equivalente a giornaliero_startfunnel() in Apps Script
    """
    logger.info("Esecuzione: giornaliero_startfunnel")

    request = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        metrics=[Metric(name='screenPageViews')],
        date_ranges=[DateRange(start_date=date, end_date=date)],
        dimension_filter=funnel_weborder_step1_filter()
    )

    response = _execute_ga4_request(client, request)

    # Processa la response per estrarre il valore
    step1_views = 0.0
    
    # Prova prima con totals
    if response.totals and len(response.totals) > 0:
        step1_views = float(response.totals[0].metric_values[0].value)
    # Altrimenti usa rows
    elif response.rows and len(response.rows) > 0:
        step1_views = float(response.rows[0].metric_values[0].value)
    else:
        logger.warning("Nessun dato per start funnel")
        return 0.0

    # Output pulito
    print("\n" + "="*80)
    print("START FUNNEL (STEP 1)")
    print("="*80)
    print(f"Date: {date}")
    print(f"Visualizzazioni: {int(step1_views)}")
    print("="*80 + "\n")
    
    logger.info(f"Visualizzazioni step 1 funnel: {step1_views}")
    
    return step1_views

# ============================================================================
# FUNZIONE 6: CR CANALIZZAZIONE
# ============================================================================

def giornaliero_cr_canalizzazione(
    conversioni: float,
    start_funnel: float
) -> pd.DataFrame:
    """
    Calcola conversion rate della canalizzazione
    Equivalente a giornaliero_cr_canalizzazione() in Apps Script
    """
    logger.info("Esecuzione: giornaliero_cr_canalizzazione")
    logger.info(f"Conversioni: {conversioni}, Start funnel: {start_funnel}")

    # DEBUG: Stampa input
    print("\n" + "="*80)
    print("GIORNALIERO_CR_CANALIZZAZIONE - Input:")
    print("="*80)
    print(f"Conversioni: {conversioni}")
    print(f"Start funnel: {start_funnel}")
    print("="*80 + "\n")

    if start_funnel > 0:
        cr_can = (conversioni / start_funnel) * 100
    else:
        cr_can = 0.0
    
    result = pd.DataFrame([{
        'Metric': 'CR_canalizzazione',
        'Value': f"{cr_can:.2f}%"
    }])
    
    logger.info(f"CR canalizzazione: {cr_can:.2f}%")
    return result

def SWI_per_commodity_type(client: BetaAnalyticsDataClient, date: str) -> pd.DataFrame:
    """
    Estrae le conversioni per tipo di commodity (dual, luce, gas) per una data specifica.
    
    Args:
        client: Client GA4 BetaAnalyticsDataClient
        date: Data in formato YYYY-MM-DD
    
    Returns:
        DataFrame con colonne:
        - Commodity_Type: tipo (dual, luce, gas)
        - Conversions: conversioni per il periodo
    """
    logger.info("Esecuzione: SWI_per_commodity_type")
    
    # Query unica con dimensione commodity
    request = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        dimensions=[Dimension(name='customEvent:commodity')],
        metrics=[Metric(name='keyEvents:weborder_residenziale')],
        date_ranges=[DateRange(start_date=date, end_date=date)]
    )

    response = _execute_ga4_request(client, request)

    # Processa response
    commodity_data = {}
    
    for row in response.rows:
        commodity_type = row.dimension_values[0].value
        conversions = int(row.metric_values[0].value)
        commodity_data[commodity_type] = conversions
    
    # Crea DataFrame
    data_rows = []
    for commodity_type in sorted(commodity_data.keys()):
        data_rows.append({
            'Commodity_Type': commodity_type,
            'Conversions': commodity_data[commodity_type]
        })
    
    df = pd.DataFrame(data_rows)
    
    # Output per debug
    print("\n" + "="*80)
    print("SWI PER COMMODITY TYPE")
    print("="*80)
    print(f"Date: {date}")
    print()
    print(df.to_string(index=False))
    print("="*80 + "\n")
    
    logger.info(f"Commodity types estratti: {len(df)}")
    
    return df

def daily_sessions_channels(client: BetaAnalyticsDataClient, date: str) -> pd.DataFrame:
    """
    Estrae le sessioni per canale (spaccato dettagliato) per una data specifica.
    
    Args:
        client: Client GA4 BetaAnalyticsDataClient
        date: Data in formato YYYY-MM-DD
    
    Returns:
        DataFrame con colonne:
        - Channel: nome del canale
        - Commodity_Sessions: sessioni commodity
        - LuceGas_Sessions: sessioni luce&gas
    """
    # Query per sessioni Commodity per canale
    request_commodity = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        dimensions=[Dimension(name="sessionCustomChannelGroup:5896515461")],
        metrics=[Metric(name='sessions')],
        date_ranges=[DateRange(start_date=date, end_date=date)],
        dimension_filter=session_commodity_filter()
    )

    commodity_response = _execute_ga4_request(client, request_commodity)

    # Query per sessioni Luce&Gas per canale
    request_lucegas = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        dimensions=[Dimension(name="sessionCustomChannelGroup:5896515461")],
        metrics=[Metric(name='sessions')],
        date_ranges=[DateRange(start_date=date, end_date=date)],
        dimension_filter=session_lucegas_filter()
    )

    lucegas_response = _execute_ga4_request(client, request_lucegas)

    # Processa response Commodity
    commodity_data = {}
    
    for row in commodity_response.rows:
        channel = row.dimension_values[0].value
        sessions = int(row.metric_values[0].value)
        commodity_data[channel] = sessions
    
    # Processa response Luce&Gas
    lucegas_data = {}
    
    for row in lucegas_response.rows:
        channel = row.dimension_values[0].value
        sessions = int(row.metric_values[0].value)
        lucegas_data[channel] = sessions
    
    # Combina i dati in un DataFrame
    all_channels = set(commodity_data.keys()) | set(lucegas_data.keys())
    
    data_rows = []
    for channel in sorted(all_channels):
        row = {
            'Channel': channel,
            'Commodity_Sessions': commodity_data.get(channel, 0),
            'LuceGas_Sessions': lucegas_data.get(channel, 0)
        }
        data_rows.append(row)
    
    df = pd.DataFrame(data_rows)
    
    # Output per debug
    print("\n" + "="*80)
    print("SESSIONI PER CANALE")
    print("="*80)
    print(f"Date: {date}")
    print()
    print(df.to_string(index=False))
    print("="*80 + "\n")
    
    return df


def daily_sessions_campaigns(client: BetaAnalyticsDataClient, date: str) -> pd.DataFrame:
    """
    Estrae le sessioni per campagna (spaccato dettagliato) per una data specifica.
    
    Args:
        client: Client GA4 BetaAnalyticsDataClient
        date: Data in formato YYYY-MM-DD
    
    Returns:
        DataFrame con colonne:
        - Campaign: nome della campagna
        - Commodity_Sessions: sessioni commodity
        - LuceGas_Sessions: sessioni luce&gas
    """
    logger.info(f"Esecuzione: daily_sessions_campaigns per {date}")
    
    # Query per sessioni Commodity per campagna
    request_commodity = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        dimensions=[Dimension(name="sessionCampaignName")],
        metrics=[Metric(name='sessions')],
        date_ranges=[DateRange(start_date=date, end_date=date)],
        dimension_filter=session_commodity_filter()
    )

    commodity_response = _execute_ga4_request(client, request_commodity)

    # Query per sessioni Luce&Gas per campagna
    request_lucegas = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        dimensions=[Dimension(name="sessionCampaignName")],
        metrics=[Metric(name='sessions')],
        date_ranges=[DateRange(start_date=date, end_date=date)],
        dimension_filter=session_lucegas_filter()
    )

    lucegas_response = _execute_ga4_request(client, request_lucegas)

    # Processa response Commodity
    commodity_data = {}
    
    for row in commodity_response.rows:
        campaign = row.dimension_values[0].value
        sessions = int(row.metric_values[0].value)
        commodity_data[campaign] = sessions
    
    # Processa response Luce&Gas
    lucegas_data = {}
    
    for row in lucegas_response.rows:
        campaign = row.dimension_values[0].value
        sessions = int(row.metric_values[0].value)
        lucegas_data[campaign] = sessions
    
    # Combina i dati in un DataFrame
    all_campaigns = set(commodity_data.keys()) | set(lucegas_data.keys())
    
    data_rows = []
    for campaign in sorted(all_campaigns):
        row = {
            'Campaign': campaign,
            'Commodity_Sessions': commodity_data.get(campaign, 0),
            'LuceGas_Sessions': lucegas_data.get(campaign, 0)
        }
        data_rows.append(row)
    
    df = pd.DataFrame(data_rows)
    
    # Output per debug
    print("\n" + "="*80)
    print("SESSIONI PER CAMPAGNA")
    print("="*80)
    print(f"Date: {date}")
    print()
    print(df.to_string(index=False))
    print("="*80 + "\n")
    
    logger.info(f"Campagne estratte: {len(df)}")
    
    return df


def extract_sessions_campaigns_delayed(target_date_str: str, db=None, skip_validation: bool = False) -> bool:
    """
    Estrae sessioni per campagna per una data specifica (D-2).
    
    GA4 ha un ritardo di ~48h per i dati per campagna, quindi questa funzione
    dovrebbe essere eseguita 2 giorni dopo la data target.
    
    Args:
        target_date_str: Data da estrarre (YYYY-MM-DD) - tipicamente D-2
        db: Istanza GA4Database per salvare direttamente (opzionale)
        skip_validation: Se True, salta validazione ritardo (default: False)
    
    Returns:
        True se successo, False altrimenti
    """
    try:
        # Validazione data (se non skippata)
        if not skip_validation:
            is_valid, message = validate_date_for_channels(target_date_str)
            if not is_valid:
                logger.warning(f"⚠️  {message}")
                logger.warning(f"⚠️  Estrazione campagne NON eseguita per {target_date_str}")
                print(f"\n⚠️  WARNING: {message}")
                print(f"⚠️  Estrazione campagne NON eseguita per {target_date_str}")
                print(f"💡 SUGGERIMENTO: Attendi almeno 48h dalla data target\n")
                return False
            else:
                logger.info(message)
        
        logger.info(f"Estrazione sessioni per campagna (delayed) per {target_date_str}")
        
        # Autenticazione (lazy)
        client = get_ga_client()
        
        # Estrai sessioni per campagna
        sessions_df = daily_sessions_campaigns(client, target_date_str)
        
        if sessions_df.empty:
            logger.warning(f"Nessun dato campagna per {target_date_str}")
            return False
        
        # Salva in database se fornito
        if db:
            campaigns = []
            for _, row in sessions_df.iterrows():
                campaigns.append({
                    'campaign': row['Campaign'],
                    'commodity_sessions': int(row['Commodity_Sessions']),
                    'lucegas_sessions': int(row['LuceGas_Sessions'])
                })
            
            success = db.insert_sessions_by_campaign(target_date_str, campaigns, replace=True)
            if success:
                logger.info(f"✓ Sessioni campagna salvate per {target_date_str}: {len(campaigns)} campagne")
                return True
            else:
                logger.error(f"Errore salvataggio sessioni campagna per {target_date_str}")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Errore estrazione sessioni campagna per {target_date_str}: {e}", exc_info=True)
        return False


# ============================================================================
# FUNZIONE PRINCIPALE
# ============================================================================

def esegui_giornaliero(period_type: str = 'ieri') -> Tuple[Dict, Dict[str, str]]:
    """
    Esegue tutte le estrazioni giornaliere
    Equivalente a esegui_giornaliero() in Apps Script
    
    Args:
        period_type: 'ieri' o 'weekend'
    
    Returns:
        Tuple contenente:
        - Dict con tutti i risultati (int, float o DataFrame)
        - Dict con le date utilizzate
    """
    logger.info("=" * 70)
    logger.info(f"INIZIO ESTRAZIONE GIORNALIERA - Tipo: {period_type}")
    logger.info("=" * 70)
    
    # Autenticazione (lazy)
    client = get_ga_client()
    
    # Calcola date
    dates = calculate_dates(period_type)
    target_date = dates['date_from']
    
    # Esegue tutte le funzioni in sequenza
    results = {}
    
    # 1. Sessioni Commodity
    results['sessioni'] = sessions(client, target_date, session_commodity_filter())

    # 1.1 Sessioni luce&gas
    results['sessioni_lucegas'] = sessions(client, target_date, session_lucegas_filter())

    # 2. SWI (conversioni)
    results['swi'] = giornaliero_swi(client, target_date)
    
    # 3. Conversion Rate
    results['cr_commodity'] = calculate_cr(results['sessioni'], results['swi'])
    results['cr_lucegas'] = calculate_cr(results['sessioni_lucegas'], results['swi'])
    
    # Output CR
    print("\n" + "="*80)
    print("CONVERSION RATE COMMODITY")
    print("="*80)
    print(f"Date: {target_date}")
    print(f"CR: {results['cr_commodity']:.2f}%")
    print("="*80 + "\n")
    
    print("\n" + "="*80)
    print("CONVERSION RATE LUCE&GAS")
    print("="*80)
    print(f"Date: {target_date}")
    print(f"CR: {results['cr_lucegas']:.2f}%")
    print("="*80 + "\n")
    
    # 4. Start Funnel
    start_funnel_value = giornaliero_startfunnel(client, target_date)
    
    # 5. CR Canalizzazione
    if results['swi'] is not None and results['swi'] > 0:
        total_swi = results['swi']
        results['cr_canalizzazione'] = giornaliero_cr_canalizzazione(
            total_swi,
            start_funnel_value
        )
        
        # 6. Prodotti (usa total_swi)
        results['prodotti'] = giornaliero_prodotti(client, target_date, total_swi)
    else:
        logger.warning("Impossibile calcolare prodotti e CR canalizzazione: SWI mancante")
        results['cr_canalizzazione'] = None
        results['prodotti'] = None
    
    # NOTA: sessioni_canale NON estratte qui (ritardo GA4 ~48h)
    # Usare extract_sessions_channels_delayed() per D-2

    logger.info("=" * 70)
    logger.info("ESTRAZIONE COMPLETATA")
    logger.info("=" * 70)

    return results, dates

# ============================================================================
# ESPORTAZIONE RISULTATI
# ============================================================================

def _convert_dict_to_dataframe(data: dict, metric_name: str = 'Metric') -> pd.DataFrame:
    """
    Converte un valore singolo (int/float) in DataFrame per compatibilità CSV legacy.
    """
    if data is None:
        return pd.DataFrame()
    
    # Se è già un dict con date_range_0 (legacy), gestiscilo
    if isinstance(data, dict) and 'date_range_0' in data:
        return pd.DataFrame([{
            'Metric': metric_name,
            'Date_Range_0': data.get('date_range_0', 0),
            'Date_Range_1': data.get('date_range_1', 0),
            'Change_Percentage': f"{data.get('change', 0):+.2f}%"
        }])
    
    # Altrimenti è un valore singolo (int/float)
    return pd.DataFrame([{
        'Metric': metric_name,
        'Value': data
    }])

def save_results_to_csv(results: Dict, output_dir: str = 'output', dates: Dict[str, str] = None):
    """
    Salva tutti i risultati in file CSV separati
    Gestisce sia dict che DataFrame
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Mapping dei nomi per metriche da dict
    metric_names = {
        'sessioni': 'Sessioni Commodity',
        'sessioni_lucegas': 'Sessioni Luce&Gas',
        'swi': 'SWI (Conversioni)',
        'cr_commodity': 'Conversion Rate Commodity',
        'cr_lucegas': 'Conversion Rate Luce&Gas'
    }
    
    saved_files = []
    
    for name, data in results.items():
        df = None
        
        # Gestisce dict (risultati legacy o valori singoli)
        if isinstance(data, dict):
            metric_name = metric_names.get(name, name.replace('_', ' ').title())
            df = _convert_dict_to_dataframe(data, metric_name)
            if dates:
                # Aggiungi informazioni sulle date nel DataFrame
                if not df.empty:
                    df['Date_From'] = dates.get('date_from', '')
                    df['Date_To'] = dates.get('date_to', '')
        
        # Gestisce valori singoli (int/float) - nuovo formato
        elif isinstance(data, (int, float)):
            metric_name = metric_names.get(name, name.replace('_', ' ').title())
            df = pd.DataFrame([{
                'Metric': metric_name,
                'Value': data,
                'Date': dates.get('date_from', '') if dates else ''
            }])
        
        # Gestisce DataFrame (prodotti, ecc.)
        elif isinstance(data, pd.DataFrame):
            df = data
        
        # Gestisce None
        elif data is None:
            logger.warning(f"✗ Saltato {name}: Dato None")
            continue
        else:
            # Prova a convertire in DataFrame se possibile
            try:
                df = pd.DataFrame([{'Value': data}])
            except:
                logger.warning(f"✗ Saltato {name}: Tipo non gestito ({type(data)})")
                continue
        
        # Salva il DataFrame
        if df is not None and not df.empty:
            filename = f"{output_dir}/{name}_{timestamp}.csv"
            df.to_csv(filename, index=False, encoding='utf-8')
            logger.info(f"✓ Salvato: {filename}")
            saved_files.append(filename)
        else:
            logger.warning(f"✗ Saltato {name}: DataFrame vuoto o None")
    
    return saved_files

def create_combined_report(results: Dict, output_dir: str = 'output', dates: Dict[str, str] = None):
    """
    Crea un singolo CSV con tutti i risultati combinati
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{output_dir}/report_completo_{timestamp}.csv"
    
    metric_names = {
        'sessioni': 'Sessioni Commodity',
        'sessioni_lucegas': 'Sessioni Luce&Gas',
        'swi': 'SWI (Conversioni)',
        'cr_commodity': 'Conversion Rate Commodity',
        'cr_lucegas': 'Conversion Rate Luce&Gas'
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        # Aggiungi header con informazioni sul report
        if dates:
            f.write(f"REPORT GIORNALIERO GA4\n")
            f.write(f"Periodo: {dates.get('date_from', '')} - {dates.get('date_to', '')}\n")
            f.write(f"Generato il: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n" + "="*80 + "\n\n")
        
        for name, data in results.items():
            df = None
            
            # Gestisce dict (legacy o valori singoli)
            if isinstance(data, dict):
                metric_name = metric_names.get(name, name.replace('_', ' ').title())
                df = _convert_dict_to_dataframe(data, metric_name)
                if dates and not df.empty:
                    df['Date_From'] = dates.get('date_from', '')
                    df['Date_To'] = dates.get('date_to', '')
            
            # Gestisce valori singoli (int/float)
            elif isinstance(data, (int, float)):
                metric_name = metric_names.get(name, name.replace('_', ' ').title())
                df = pd.DataFrame([{
                    'Metric': metric_name,
                    'Value': data,
                    'Date': dates.get('date_from', '') if dates else ''
                }])
            
            # Gestisce DataFrame
            elif isinstance(data, pd.DataFrame):
                df = data
            
            # Salva la sezione
            if df is not None and not df.empty:
                f.write(f"\n=== {name.upper().replace('_', ' ')} ===\n")
                df.to_csv(f, index=False)
                f.write("\n")
    
    logger.info(f"✓ Report completo salvato: {filename}")
    return filename

# ============================================================================
# DATABASE STORAGE (NEW)
# ============================================================================

def save_to_database(results: Dict, date: str, db, redis_cache=None, dates: Dict[str, str] = None):
    """
    Salva risultati estrazione in database SQLite e Redis cache.
    
    Sostituisce save_results_to_csv per nuovo workflow database.
    
    Args:
        results: Dict con risultati da esegui_giornaliero
        date: Data da salvare (YYYY-MM-DD)
        db: Istanza GA4Database
        redis_cache: Istanza GA4RedisCache (opzionale)
        dates: Dict con date per logging (opzionale)
    
    Returns:
        True se successo, False altrimenti
    """
    try:
        # Prepara metriche raw per database
        # I risultati sono ora int/float diretti invece di dict
        metrics = {
            'sessioni_commodity': results.get('sessioni', 0) if isinstance(results.get('sessioni'), int) else 0,
            'sessioni_lucegas': results.get('sessioni_lucegas', 0) if isinstance(results.get('sessioni_lucegas'), int) else 0,
            'swi_conversioni': results.get('swi', 0) if isinstance(results.get('swi'), int) else 0,
            'cr_commodity': results.get('cr_commodity', 0.0) if isinstance(results.get('cr_commodity'), (int, float)) else 0.0,
            'cr_lucegas': results.get('cr_lucegas', 0.0) if isinstance(results.get('cr_lucegas'), (int, float)) else 0.0,
            'cr_canalizzazione': 0.0,
            'start_funnel': 0
        }
        
        # Estrai CR canalizzazione se disponibile
        if results.get('cr_canalizzazione') is not None:
            cr_can_df = results['cr_canalizzazione']
            if isinstance(cr_can_df, pd.DataFrame) and not cr_can_df.empty:
                cr_can_str = cr_can_df.iloc[0]['Value']
                metrics['cr_canalizzazione'] = float(cr_can_str.replace('%', ''))
        
        # Estrai start_funnel se disponibile
        # Calcoliamo dal CR canalizzazione se disponibile
        if results.get('swi') and metrics['cr_canalizzazione'] > 0:
            total_swi = results['swi'] if isinstance(results['swi'], int) else 0
            if total_swi > 0:
                metrics['start_funnel'] = int(total_swi / (metrics['cr_canalizzazione'] / 100))
        
        # Salva metriche in SQLite
        logger.info(f"Salvataggio metriche per {date}: {metrics}")
        success = db.insert_daily_metrics(date, metrics, replace=True)
        
        if not success:
            logger.error(f"Errore salvataggio metriche in SQLite per {date}")
            raise Exception(f"insert_daily_metrics failed for {date} with metrics: {metrics}")
        
        logger.info(f"✓ Metriche salvate in SQLite per {date}")
        
        # Prepara prodotti
        products = []
        if results.get('prodotti') is not None and not results['prodotti'].empty:
            for _, row in results['prodotti'].iterrows():
                percentage_str = row['Percentage'].replace('%', '')
                products.append({
                    'product_name': row['Product'],
                    'total_conversions': float(row['Total']),
                    'percentage': float(percentage_str)
                })
        
        # Salva prodotti in SQLite
        if products:
            success = db.insert_products(date, products, replace=True)
            if success:
                logger.info(f"✓ Prodotti salvati in SQLite per {date}: {len(products)} prodotti")
        
        # NOTA: sessioni_canale non salvate qui (ritardo GA4 ~48h)
        # Usare extract_sessions_channels_delayed() separatamente
        
        # Salva in Redis cache (se disponibile)
        if redis_cache:
            try:
                cache_metrics = {k: v for k, v in metrics.items()}
                redis_cache.set_metrics(date, cache_metrics)
                logger.info(f"✓ Metriche cached in Redis per {date}")
            except Exception as e:
                logger.warning(f"Redis cache non disponibile: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Errore salvataggio database per {date}: {e}", exc_info=True)
        return False


def validate_date_for_channels(target_date_str: str, min_delay_days: int = 2) -> tuple:
    """
    Valida che una data sia sufficientemente vecchia per avere dati canale GA4.
    
    Args:
        target_date_str: Data da validare (YYYY-MM-DD)
        min_delay_days: Ritardo minimo in giorni (default: 2)
    
    Returns:
        Tuple (is_valid: bool, message: str)
    """
    from datetime import datetime, timedelta
    
    target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    min_date = today - timedelta(days=min_delay_days)
    
    if target_date > min_date:
        days_diff = (today - target_date).days
        return False, f"Data troppo recente ({target_date_str}). GA4 richiede ~48h di ritardo. Giorni trascorsi: {days_diff}, richiesti: {min_delay_days}"
    
    return True, f"Data valida per estrazione canali ({target_date_str})"


def extract_sessions_channels_delayed(target_date_str: str, db=None, skip_validation: bool = False) -> bool:
    """
    Estrae sessioni per canale per una data specifica (D-2).
    
    GA4 ha un ritardo di ~48h per i dati per canale, quindi questa funzione
    dovrebbe essere eseguita 2 giorni dopo la data target.
    
    Args:
        target_date_str: Data da estrarre (YYYY-MM-DD) - tipicamente D-2
        db: Istanza GA4Database per salvare direttamente (opzionale)
        skip_validation: Se True, salta validazione ritardo (default: False)
    
    Returns:
        True se successo, False altrimenti
    """
    try:
        # Validazione data (se non skippata)
        if not skip_validation:
            is_valid, message = validate_date_for_channels(target_date_str)
            if not is_valid:
                logger.warning(f"⚠️  {message}")
                logger.warning(f"⚠️  Estrazione canali NON eseguita per {target_date_str}")
                print(f"\n⚠️  WARNING: {message}")
                print(f"⚠️  Estrazione canali NON eseguita per {target_date_str}")
                print(f"💡 SUGGERIMENTO: Attendi almeno 48h dalla data target\n")
                return False
            else:
                logger.info(message)
        
        logger.info(f"Estrazione sessioni per canale (delayed) per {target_date_str}")
        
        # Autenticazione (lazy)
        client = get_ga_client()
        
        # Estrai sessioni per canale
        sessions_df = daily_sessions_channels(client, target_date_str)
        
        if sessions_df.empty:
            logger.warning(f"Nessun dato canale per {target_date_str}")
            return False
        
        # Salva in database se fornito
        if db:
            channels = []
            for _, row in sessions_df.iterrows():
                channels.append({
                    'channel': row['Channel'],
                    'commodity_sessions': int(row['Commodity_Sessions']),
                    'lucegas_sessions': int(row['LuceGas_Sessions'])
                })
            
            success = db.insert_sessions_by_channel(target_date_str, channels, replace=True)
            if success:
                logger.info(f"✓ Sessioni canale salvate per {target_date_str}: {len(channels)} canali")
                return True
            else:
                logger.error(f"Errore salvataggio sessioni canale per {target_date_str}")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Errore estrazione sessioni canale per {target_date_str}: {e}", exc_info=True)
        return False


def extract_for_date(target_date_str: str) -> Tuple[Dict, Dict[str, str]]:
    """
    Estrae dati GA4 per una data specifica.
    
    Utile per backfill o ri-estrazione di date specifiche.
    
    NOTA: Non include sessioni_canale (ritardo GA4 ~48h).
    Usare extract_sessions_channels_delayed() separatamente per D-2.
    
    Args:
        target_date_str: Data da estrarre (YYYY-MM-DD)
    
    Returns:
        Tuple (results, dates) come esegui_giornaliero
    """
    from datetime import datetime
    
    target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
    
    dates = {
        'date_from': target_date_str,
        'date_to': target_date_str
    }
    
    logger.info(f"Estrazione per data specifica: {target_date_str}")
    
    # Autenticazione (lazy)
    client = get_ga_client()
    
    # Esegue estrazione
    results = {}
    
    # 1. Sessioni Commodity
    results['sessioni'] = sessions(client, target_date_str, session_commodity_filter())
    
    # 1.1 Sessioni luce&gas
    results['sessioni_lucegas'] = sessions(client, target_date_str, session_lucegas_filter())
    
    # 2. SWI (conversioni)
    results['swi'] = giornaliero_swi(client, target_date_str)
    
    # 3. Conversion Rate
    results['cr_commodity'] = calculate_cr(results['sessioni'], results['swi'])
    results['cr_lucegas'] = calculate_cr(results['sessioni_lucegas'], results['swi'])
    
    # 4. Start Funnel
    start_funnel_value = giornaliero_startfunnel(client, target_date_str)
    
    # 5. CR Canalizzazione
    if results['swi'] is not None and results['swi'] > 0:
        total_swi = results['swi']
        results['cr_canalizzazione'] = giornaliero_cr_canalizzazione(
            total_swi,
            start_funnel_value
        )
        
        # 6. Prodotti
        results['prodotti'] = giornaliero_prodotti(client, target_date_str, total_swi)
    else:
        logger.warning("Impossibile calcolare prodotti e CR canalizzazione: SWI mancante")
        results['cr_canalizzazione'] = None
        results['prodotti'] = None
    
    # NOTA: sessioni_canale NON estratte qui (ritardo GA4 ~48h)
    # Usare extract_sessions_channels_delayed() per D-2
    
    return results, dates

# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Punto di ingresso principale dello script
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Estrazione dati giornaliera da GA4'
    )
    parser.add_argument(
        '--period',
        choices=['ieri', 'weekend'],
        default='ieri',
        help='Tipo di periodo da estrarre (default: ieri)'
    )
    parser.add_argument(
        '--output-dir',
        default='output',
        help='Directory per i file CSV (default: output)'
    )
    parser.add_argument(
        '--combined',
        action='store_true',
        help='Crea anche un report combinato unico'
    )
    
    args = parser.parse_args()
    
    try:
        # Esegui estrazione
        results = esegui_giornaliero(args.period)
        
        # Salva risultati
        save_results_to_csv(results, args.output_dir)
        
        if args.combined:
            create_combined_report(results, args.output_dir)
        
        logger.info("✓ Script completato con successo")
        return 0
        
    except Exception as e:
        logger.error(f"✗ Errore durante l'esecuzione: {e}", exc_info=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())