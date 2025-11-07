#!/usr/bin/env python3
"""
Migrazione da Google Apps Script a Python per estrazione dati GA4
Traduce tutte le funzioni dello script originale
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
from ga4_extraction.filters import session_commodity_filter, session_lucegas_filter, funnel_weborder_step1_filter, commodity_type_filter
from ga4_extraction.config import get_credentials

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# Imposta questi valori con i tuoi dati
PROPERTY_ID = "281687433"
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ga4_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# AUTENTICAZIONE OAUTH
# ============================================================================

creds = get_credentials()
client = BetaAnalyticsDataClient(credentials=creds)




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

    response = client.run_report(request)

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

    response = client.run_report(request)

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

    response = client.run_report(request)

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

    response = client.run_report(request)

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

    response = client.run_report(request)

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

    commodity_response = client.run_report(request_commodity)

    # Query per sessioni Luce&Gas per canale
    request_lucegas = RunReportRequest(
        property=f'properties/{PROPERTY_ID}',
        dimensions=[Dimension(name="sessionCustomChannelGroup:5896515461")],
        metrics=[Metric(name='sessions')],
        date_ranges=[DateRange(start_date=date, end_date=date)],
        dimension_filter=session_lucegas_filter()
    )

    lucegas_response = client.run_report(request_lucegas)

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
    
    # Autenticazione
    creds = get_credentials()
    client = BetaAnalyticsDataClient(credentials=creds)
    
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

    # 5. Sessioni per canale
    results['sessioni_canale'] = daily_sessions_channels(client, target_date)
    
    # 6. CR Canalizzazione
    if results['swi'] is not None and results['swi'] > 0:
        total_swi = results['swi']
        results['cr_canalizzazione'] = giornaliero_cr_canalizzazione(
            total_swi,
            start_funnel_value
        )
        
        # 7. Prodotti (usa total_swi)
        results['prodotti'] = giornaliero_prodotti(client, target_date, total_swi)
    else:
        logger.warning("Impossibile calcolare prodotti e CR canalizzazione: SWI mancante")
        results['cr_canalizzazione'] = None
        results['prodotti'] = None

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
        success = db.insert_daily_metrics(date, metrics, replace=True)
        
        if not success:
            logger.error(f"Errore salvataggio metriche in SQLite per {date}")
            return False
        
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
        
        # Prepara sessioni per canale
        channels = []
        if results.get('sessioni_canale') is not None and isinstance(results['sessioni_canale'], pd.DataFrame):
            if not results['sessioni_canale'].empty:
                for _, row in results['sessioni_canale'].iterrows():
                    channels.append({
                        'channel': row['Channel'],
                        'commodity_sessions': int(row['Commodity_Sessions']),
                        'lucegas_sessions': int(row['LuceGas_Sessions'])
                    })
        
        # Salva sessioni per canale in SQLite
        if channels:
            success = db.insert_sessions_by_channel(date, channels, replace=True)
            if success:
                logger.info(f"✓ Sessioni per canale salvate in SQLite per {date}: {len(channels)} canali")
        
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


def extract_for_date(target_date_str: str) -> Tuple[Dict, Dict[str, str]]:
    """
    Estrae dati GA4 per una data specifica.
    
    Utile per backfill o ri-estrazione di date specifiche.
    
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
    
    # Autenticazione
    creds = get_credentials()
    client = BetaAnalyticsDataClient(credentials=creds)
    
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