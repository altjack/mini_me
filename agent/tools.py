"""Tool functions for the agent to interact with GA4 extraction module."""

import sys
import os
import logging
import glob
import yaml
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional
import pandas
from datapizza.tools import tool

# Aggiungi il percorso del modulo ga4_extraction al path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from ga4_extraction.extraction import (
    esegui_giornaliero, 
    calculate_dates,
    save_results_to_csv,
    create_combined_report
)
from ga4_extraction.database import GA4Database
from ga4_extraction.redis_cache import GA4RedisCache

# Configurazione del logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ga4_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@tool
def get_daily_report(date: str) -> str:
    """Get the daily report for a given date from database.
    
    Args:
        date: Date in YYYY-MM-DD format.
    
    Returns:
        Formatted string containing the daily report.
    """
    try:
        from datetime import datetime, timedelta
        
        # Converte la data fornita
        requested_date = datetime.strptime(date, '%Y-%m-%d')
        target_date_str = date
        
        db, cache = _get_db_instances()
        
        # Recupera metriche dal database
        current = db.get_metrics(target_date_str)
        if not current:
            return f"❌ Nessun dato disponibile per {target_date_str}"
        
        # Calcola confronto con 7 giorni prima
        comparison = db.calculate_comparison(target_date_str, days_ago=7)
        
        if not comparison or not comparison.get('previous'):
            prev_info = "Nessun dato di confronto disponibile"
            comp_info = {}
            prev = {}
        else:
            prev = comparison['previous']
            comp_info = comparison.get('comparison', {})
            prev_info = f"Confrontato con: {comparison['previous_date']}"
        
        # Calcola giorno della settimana e mese in italiano
        giorni_settimana = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']
        mesi = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 
                'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']
        giorno_nome = giorni_settimana[requested_date.weekday()]
        mese_nome = mesi[requested_date.month - 1]
        data_formattata = f"{giorno_nome.capitalize()} {requested_date.day} {mese_nome}"
        
        # Formatta report
        report = f"""# Report Giornaliero GA4 - {data_formattata} ({target_date_str})
{prev_info}
### Generato il: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Sessioni

**Commodity:**
- Corrente: {current['sessioni_commodity']:,}
{f"- Precedente: {prev.get('sessioni_commodity', 0):,}" if comparison and comparison.get('previous') else ""}
{f"- Variazione: {comp_info.get('sessioni_commodity_change', 0):+.2f}%" if comp_info else ""}

**Luce&Gas:**
- Corrente: {current['sessioni_lucegas']:,}
{f"- Precedente: {prev.get('sessioni_lucegas', 0):,}" if comparison and comparison.get('previous') else ""}
{f"- Variazione: {comp_info.get('sessioni_lucegas_change', 0):+.2f}%" if comp_info else ""}

## Conversioni

**SWI (Switch In):**
- Corrente: {current['swi_conversioni']:,}
{f"- Precedente: {prev.get('swi_conversioni', 0):,}" if comparison and comparison.get('previous') else ""}
{f"- Variazione: {comp_info.get('swi_conversioni_change', 0):+.2f}%" if comp_info else ""}

## Conversion Rates

**CR Commodity:**
- Corrente: {current['cr_commodity']:.2f}%
{f"- Precedente: {prev.get('cr_commodity', 0):.2f}%" if comparison and comparison.get('previous') else ""}
{f"- Variazione: {comp_info.get('cr_commodity_change', 0):+.2f}%" if comp_info else ""}

**CR Luce&Gas:**
- Corrente: {current['cr_lucegas']:.2f}%
{f"- Precedente: {prev.get('cr_lucegas', 0):.2f}%" if comparison and comparison.get('previous') else ""}
{f"- Variazione: {comp_info.get('cr_lucegas_change', 0):+.2f}%" if comp_info else ""}

**CR Canalizzazione:**
- Corrente: {current['cr_canalizzazione']:.2f}%

**Start Funnel:**
- Corrente: {current['start_funnel']:,}
"""
        
        # Prodotti
        products = db.get_products(target_date_str)
        if products:
            report += "\n## Performance Prodotti\n\n"
            for prod in products:
                report += f"- **{prod['product_name'].capitalize()}**: {int(prod['total_conversions'])} conversioni ({prod['percentage']:.2f}%)\n"
        
        # Sessioni per canale
        channels = db.get_sessions_by_channel(target_date_str)
        if channels:
            report += "\n## Sessioni per Canale\n\n"
            for ch in channels:
                report += f"- **{ch['channel']}**: {ch['commodity_sessions']:,} commodity, {ch['lucegas_sessions']:,} luce&gas\n"
        
        db.close()
        if cache:
            cache.close()
        
        return report
        
    except Exception as e:
        logger.error(f"Errore nella generazione del report giornaliero: {e}", exc_info=True)
        return f"Errore nella generazione del report giornaliero: {e}"

@tool
def get_metrics_summary(period_days: int = 1) -> str:
    """Get a summary of metrics for the last N days from database.
    
    Args:
        period_days: Number of days to include in the summary.
    
    Returns:
        Formatted string containing the metrics summary.
    """
    try:
        from datetime import datetime, timedelta
        
        db, cache = _get_db_instances()
        
        # Calcola date: ultimo giorno disponibile (ieri)
        yesterday = datetime.now() - timedelta(days=1)
        target_date_str = yesterday.strftime('%Y-%m-%d')
        
        # Recupera metriche dal database
        current = db.get_metrics(target_date_str)
        if not current:
            return f"❌ Nessun dato disponibile per {target_date_str}"
        
        # Calcola confronto con 7 giorni prima
        comparison = db.calculate_comparison(target_date_str, days_ago=7)
        
        if not comparison or not comparison.get('previous'):
            prev_info = "Nessun dato di confronto disponibile"
            comp_info = {}
        else:
            prev = comparison['previous']
            comp_info = comparison.get('comparison', {})
            prev_info = f"Confrontato con: {comparison['previous_date']}"
        
        # Calcola giorno della settimana e mese in italiano
        giorni_settimana = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']
        mesi = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 
                'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']
        giorno_nome = giorni_settimana[yesterday.weekday()]
        mese_nome = mesi[yesterday.month - 1]
        data_formattata = f"{giorno_nome.capitalize()} {yesterday.day} {mese_nome}"
        
        # Formatta report
        report = f"""# Report Giornaliero GA4
## Data: {data_formattata} ({target_date_str})
{prev_info}
### Generato il: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Sessioni

**Commodity:**
- Corrente: {current['sessioni_commodity']:,}
{f"- Precedente: {prev['sessioni_commodity']:,}" if comparison and comparison.get('previous') else ""}
{f"- Variazione: {comp_info.get('sessioni_commodity_change', 0):+.2f}%" if comp_info else ""}

**Luce&Gas:**
- Corrente: {current['sessioni_lucegas']:,}
{f"- Precedente: {prev['sessioni_lucegas']:,}" if comparison and comparison.get('previous') else ""}
{f"- Variazione: {comp_info.get('sessioni_lucegas_change', 0):+.2f}%" if comp_info else ""}

## Conversioni

**SWI (Switch In):**
- Corrente: {current['swi_conversioni']:,}
{f"- Precedente: {prev['swi_conversioni']:,}" if comparison and comparison.get('previous') else ""}
{f"- Variazione: {comp_info.get('swi_conversioni_change', 0):+.2f}%" if comp_info else ""}

## Conversion Rates

**CR Commodity:**
- Corrente: {current['cr_commodity']:.2f}%
{f"- Precedente: {prev['cr_commodity']:.2f}%" if comparison and comparison.get('previous') else ""}
{f"- Variazione: {comp_info.get('cr_commodity_change', 0):+.2f}%" if comp_info else ""}

**CR Luce&Gas:**
- Corrente: {current['cr_lucegas']:.2f}%
{f"- Precedente: {prev['cr_lucegas']:.2f}%" if comparison and comparison.get('previous') else ""}
{f"- Variazione: {comp_info.get('cr_lucegas_change', 0):+.2f}%" if comp_info else ""}

**CR Canalizzazione:**
- Corrente: {current['cr_canalizzazione']:.2f}%

**Start Funnel:**
- Corrente: {current['start_funnel']:,}
"""
        
        # Prodotti
        products = db.get_products(target_date_str)
        if products:
            report += "\n## Performance Prodotti\n\n"
            for prod in products:
                report += f"- **{prod['product_name'].capitalize()}**: {int(prod['total_conversions'])} conversioni ({prod['percentage']:.2f}%)\n"
        
        # Sessioni per canale
        channels = db.get_sessions_by_channel(target_date_str)
        if channels:
            report += "\n## Sessioni per Canale\n\n"
            for ch in channels[:10]:  # Top 10 canali
                report += f"- **{ch['channel']}**: {ch['commodity_sessions']:,} commodity, {ch['lucegas_sessions']:,} luce&gas\n"
        
        db.close()
        if cache:
            cache.close()
        
        return report
        
    except Exception as e:
        logger.error(f"Errore nella generazione del summary: {e}", exc_info=True)
        return f"Errore nella generazione del summary: {e}"


@tool
def get_product_performance(date: str) -> str:
    """Get product performance for a given date from database.
    
    Args:
        date: Date in YYYY-MM-DD format.
    
    Returns:
        Formatted string containing the product performance.
    """
    try:
        from datetime import datetime
        
        target_date_str = date
        
        db, cache = _get_db_instances()
        
        # Recupera prodotti dal database
        products = db.get_products(target_date_str)
        
        if not products:
            return f"❌ Nessun dato sui prodotti disponibile per {target_date_str}"
        
        # Formatta report
        report = f"""# Performance Prodotti - {target_date_str}

"""
        for prod in products:
            report += f"- **{prod['product_name'].capitalize()}**: {int(prod['total_conversions'])} conversioni ({prod['percentage']:.2f}%)\n"
        
        db.close()
        if cache:
            cache.close()
        
        return report
        
    except Exception as e:
        logger.error(f"Errore nella generazione del report prodotti: {e}", exc_info=True)
        return f"Errore nella generazione del report prodotti: {e}"


@tool
def compare_periods(start_date: str, end_date: str, compare_start: str, compare_end: str) -> str:
    """Compare metrics between two different periods from database.
    
    Calculates averages and totals for each period and compares them.
    
    Args:
        start_date: Start date of first period in YYYY-MM-DD format.
        end_date: End date of first period in YYYY-MM-DD format.
        compare_start: Start date of comparison period in YYYY-MM-DD format.
        compare_end: End date of comparison period in YYYY-MM-DD format.
    
    Returns:
        Formatted string containing the comparison report.
    """
    try:
        from datetime import datetime
        
        db, cache = _get_db_instances()
        
        # Recupera dati per periodo 1
        period1_data = db.get_date_range(start_date, end_date)
        if not period1_data:
            return f"❌ Nessun dato disponibile per periodo 1: {start_date} - {end_date}"
        
        # Recupera dati per periodo 2
        period2_data = db.get_date_range(compare_start, compare_end)
        if not period2_data:
            return f"❌ Nessun dato disponibile per periodo 2: {compare_start} - {compare_end}"
        
        # Funzioni helper per calcoli
        def avg_metric(data, metric):
            """Calcola media di una metrica su un periodo."""
            values = [d[metric] for d in data if metric in d]
            return sum(values) / len(values) if values else 0
        
        def sum_metric(data, metric):
            """Calcola somma di una metrica su un periodo."""
            values = [d[metric] for d in data if metric in d]
            return sum(values) if values else 0
        
        def calc_change(current, previous):
            """Calcola variazione percentuale."""
            if previous == 0:
                return 0.0
            return ((current - previous) / previous) * 100
        
        # Metriche da confrontare
        metrics_to_compare = [
            ('sessioni_commodity', 'Sessioni Commodity', 'avg'),
            ('sessioni_lucegas', 'Sessioni Luce&Gas', 'avg'),
            ('swi_conversioni', 'Conversioni SWI', 'sum'),
            ('cr_commodity', 'CR Commodity', 'avg'),
            ('cr_lucegas', 'CR Luce&Gas', 'avg'),
            ('cr_canalizzazione', 'CR Canalizzazione', 'avg'),
        ]
        
        # Formatta report
        report = f"""# Confronto Periodi
## Periodo 1: {start_date} - {end_date} ({len(period1_data)} giorni)
## Periodo 2: {compare_start} - {compare_end} ({len(period2_data)} giorni)
### Generato il: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Confronto Metriche

"""
        
        for metric_key, metric_name, calc_type in metrics_to_compare:
            if calc_type == 'avg':
                period1_val = avg_metric(period1_data, metric_key)
                period2_val = avg_metric(period2_data, metric_key)
            else:  # sum
                period1_val = sum_metric(period1_data, metric_key)
                period2_val = sum_metric(period2_data, metric_key)
            
            change = calc_change(period1_val, period2_val)
            
            # Formattazione in base al tipo
            if 'cr_' in metric_key or 'CR' in metric_name:
                format_str = "{:.2f}%"
            else:
                format_str = "{:,.0f}"
            
            report += f"""**{metric_name}:**
- Periodo 1: {format_str.format(period1_val)}
- Periodo 2: {format_str.format(period2_val)}
- Variazione: {change:+.2f}%

"""
        
        # Confronto prodotti (somma conversioni per prodotto)
        # Raccogli tutti i prodotti di entrambi i periodi
        period1_products = {}
        for day_data in period1_data:
            day_products = db.get_products(day_data['date'])
            for prod in day_products:
                name = prod['product_name']
                if name not in period1_products:
                    period1_products[name] = 0
                period1_products[name] += prod['total_conversions']
        
        period2_products = {}
        for day_data in period2_data:
            day_products = db.get_products(day_data['date'])
            for prod in day_products:
                name = prod['product_name']
                if name not in period2_products:
                    period2_products[name] = 0
                period2_products[name] += prod['total_conversions']
        
        # Confronta prodotti comuni
        all_products = set(period1_products.keys()) | set(period2_products.keys())
        if all_products:
            report += "\n## Confronto Prodotti (Conversioni Totali)\n\n"
            for product_name in sorted(all_products):
                p1_val = period1_products.get(product_name, 0)
                p2_val = period2_products.get(product_name, 0)
                change = calc_change(p1_val, p2_val) if p2_val > 0 else 0
                report += f"- **{product_name.capitalize()}**: Periodo 1: {p1_val:.0f}, Periodo 2: {p2_val:.0f}, Variazione: {change:+.2f}%\n"
        
        db.close()
        if cache:
            cache.close()
        
        return report
        
    except Exception as e:
        logger.error(f"Errore nella generazione del confronto: {e}", exc_info=True)
        return f"Errore nella generazione del confronto: {e}"


def format_results(results: Dict, dates: Dict) -> str:
    """
    DEPRECATED: Funzione helper legacy per formato vecchio.
    
    Non più utilizzata dai tool principali. Mantenuta per retrocompatibilità.
    
    Args:
        results: Results from esegui_giornaliero function (formato vecchio).
        dates: Date dictionary with period information (formato vecchio).
    
    Returns:
        Formatted string with the results.
    """
    report = "# Report Giornaliero GA4\n\n"
    report += f"**Data periodo principale**: {dates['date_from1']}\n\n"
    report += f"**Data periodo di confronto**: {dates['date_from2']}\n\n"
    
    # Formatta le sessioni
    if results.get('sessioni') is not None:
        report += "## Sessioni Commodity\n\n"
        report += f"- **Periodo principale**: {results['sessioni']['date_range_0']} sessioni\n"
        report += f"- **Periodo confronto**: {results['sessioni']['date_range_1']} sessioni\n"
        report += f"- **Variazione**: {results['sessioni']['change']:+.2f}%\n\n"
    
    # Formatta le sessioni luce&gas
    if results.get('sessioni_lucegas') is not None:
        report += "## Sessioni Luce&Gas\n\n"
        report += f"- **Periodo principale**: {results['sessioni_lucegas']['date_range_0']} sessioni\n"
        report += f"- **Periodo confronto**: {results['sessioni_lucegas']['date_range_1']} sessioni\n"
        report += f"- **Variazione**: {results['sessioni_lucegas']['change']:+.2f}%\n\n"
    
    # Formatta le conversioni
    if results.get('swi') is not None:
        report += "## Conversioni SWI\n\n"
        report += f"- **Periodo principale**: {results['swi']['date_range_0']} conversioni\n"
        report += f"- **Periodo confronto**: {results['swi']['date_range_1']} conversioni\n"
        report += f"- **Variazione**: {results['swi']['change']:+.2f}%\n\n"
    
    # Formatta i conversion rate
    if results.get('cr_commodity') is not None:
        report += "## Conversion Rate Commodity\n\n"
        report += f"- **Periodo principale**: {results['cr_commodity']['date_range_0']:.2f}%\n"
        report += f"- **Periodo confronto**: {results['cr_commodity']['date_range_1']:.2f}%\n"
        report += f"- **Variazione**: {results['cr_commodity']['change']:+.2f}%\n\n"
    
    if results.get('cr_lucegas') is not None:
        report += "## Conversion Rate Luce&Gas\n\n"
        report += f"- **Periodo principale**: {results['cr_lucegas']['date_range_0']:.2f}%\n"
        report += f"- **Periodo confronto**: {results['cr_lucegas']['date_range_1']:.2f}%\n"
        report += f"- **Variazione**: {results['cr_lucegas']['change']:+.2f}%\n\n"
    
    # Formatta i prodotti
    if results.get('prodotti') is not None and not results['prodotti'].empty:
        report += "## Prodotti\n\n"
        report += format_dataframe(results['prodotti'], "Prodotti")
        report += "\n\n"
    
    return report


    


# ============================================================================
# NEW DATABASE TOOLS
# ============================================================================

def _get_db_instances():
    """
    Helper per ottenere istanze database e cache.
    Carica config e crea connessioni.
    """
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    db_config = config.get('database', {})
    
    # SQLite
    db_path = db_config.get('sqlite', {}).get('path', 'data/ga4_data.db')
    db = GA4Database(db_path)
    
    # Redis (opzionale)
    try:
        redis_config = db_config.get('redis', {})
        cache = GA4RedisCache(
            host=redis_config.get('host', 'localhost'),
            port=redis_config.get('port', 6379),
            db=redis_config.get('db', 1),
            key_prefix=redis_config.get('key_prefix', 'ga4:metrics:'),
            ttl_days=redis_config.get('ttl_days', 14)
        )
    except Exception as e:
        logger.warning(f"Redis non disponibile: {e}")
        cache = None
    
    return db, cache


@tool
def get_ga4_metrics(date: str = None, compare_days_ago: int = 7) -> str:
    """Get GA4 metrics for a specific date with dynamic comparison.
    
    Reads from Redis cache (fast) with SQLite fallback.
    Calculates comparison percentages dynamically.
    
    Args:
        date: Date in YYYY-MM-DD format (default: yesterday)
        compare_days_ago: Days ago to compare with (default: 7)
    
    Returns:
        Formatted string with current metrics and comparison.
    """
    try:
        # Date di default: ieri
        if date is None:
            yesterday = datetime.now() - timedelta(days=1)
            date = yesterday.strftime('%Y-%m-%d')
        
        db, cache = _get_db_instances()
        
        # Prova Redis cache
        current = None
        if cache:
            current = cache.get_metrics(date)
            if current:
                logger.info(f"Cache HIT per {date}")
        
        # Fallback SQLite
        if not current:
            current = db.get_metrics(date)
            logger.info(f"Database read per {date}")
        
        if not current:
            return f"❌ Nessun dato disponibile per {date}.\n\nVerifica che i dati siano stati estratti."
        
        # Calcola comparison dinamico
        comparison = db.calculate_comparison(date, compare_days_ago)
        
        if not comparison or not comparison['previous']:
            # Nessun confronto disponibile
            report = f"""# Report GA4 - {date}

**Metriche del giorno:**

- **Sessioni Commodity**: {current['sessioni_commodity']}
- **Sessioni Luce&Gas**: {current['sessioni_lucegas']}
- **Conversioni SWI**: {current['swi_conversioni']}
- **CR Commodity**: {current['cr_commodity']:.2f}%
- **CR Luce&Gas**: {current['cr_lucegas']:.2f}%
- **CR Canalizzazione**: {current['cr_canalizzazione']:.2f}%
- **Start Funnel**: {current['start_funnel']}

⚠️ Dati di confronto non disponibili per {compare_days_ago} giorni fa.
"""
        else:
            # Con confronto
            comp = comparison['comparison']
            prev = comparison['previous']
            prev_date = comparison['previous_date']
            
            report = f"""# Report GA4 - {date}
Confronto con {prev_date} ({compare_days_ago} giorni fa)

## Sessioni

**Commodity:**
- Corrente: {current['sessioni_commodity']} 
- Precedente: {prev['sessioni_commodity']}
- Variazione: {comp['sessioni_commodity_change']:+.2f}%

**Luce&Gas:**
- Corrente: {current['sessioni_lucegas']}
- Precedente: {prev['sessioni_lucegas']}
- Variazione: {comp['sessioni_lucegas_change']:+.2f}%

## Conversioni

**SWI (Switch In):**
- Corrente: {current['swi_conversioni']}
- Precedente: {prev['swi_conversioni']}
- Variazione: {comp['swi_conversioni_change']:+.2f}%

## Conversion Rates

**CR Commodity:**
- Corrente: {current['cr_commodity']:.2f}%
- Precedente: {prev['cr_commodity']:.2f}%
- Variazione: {comp['cr_commodity_change']:+.2f}%

**CR Luce&Gas:**
- Corrente: {current['cr_lucegas']:.2f}%
- Precedente: {prev['cr_lucegas']:.2f}%
- Variazione: {comp['cr_lucegas_change']:+.2f}%

**CR Canalizzazione:**
- Corrente: {current['cr_canalizzazione']:.2f}%

**Start Funnel:**
- Corrente: {current['start_funnel']}
"""
        
        # Prodotti
        products = db.get_products(date)
        if products:
            report += "\n## Performance Prodotti\n\n"
            for prod in products:
                report += f"- **{prod['product_name'].capitalize()}**: {int(prod['total_conversions'])} conversioni ({prod['percentage']:.2f}%)\n"
        
        db.close()
        if cache:
            cache.close()
        
        return report
        
    except Exception as e:
        logger.error(f"Errore get_ga4_metrics: {e}", exc_info=True)
        return f"❌ Errore recupero metriche: {e}"


@tool
def get_metrics_trend(days: int = 7, metric: str = "swi_conversioni") -> str:
    """Get trend analysis for a specific metric over the last N days.
    
    Calculates average, min, max, and growth rate.
    
    Args:
        days: Number of days to analyze (default: 7)
        metric: Metric to analyze (default: swi_conversioni)
                Options: sessioni_commodity, sessioni_lucegas, swi_conversioni,
                        cr_commodity, cr_lucegas, cr_canalizzazione
    
    Returns:
        Formatted string with trend analysis.
    """
    try:
        db, cache = _get_db_instances()
        
        # Calcola date range
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=days - 1)
        
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        # Recupera dati
        metrics = db.get_date_range(start_str, end_str)
        
        if not metrics:
            return f"❌ Nessun dato disponibile per ultimi {days} giorni."
        
        # Estrai valori della metrica
        values = [m[metric] for m in metrics if metric in m]
        dates = [m['date'] for m in metrics]
        
        if not values:
            return f"❌ Metrica '{metric}' non trovata."
        
        # Statistiche
        avg_val = sum(values) / len(values)
        min_val = min(values)
        max_val = max(values)
        
        # Trend (primo vs ultimo)
        if len(values) >= 2:
            first_val = values[0]
            last_val = values[-1]
            if first_val > 0:
                growth_rate = ((last_val - first_val) / first_val) * 100
            else:
                growth_rate = 0
        else:
            growth_rate = 0
        
        report = f"""# Analisi Trend - {metric.replace('_', ' ').title()}
Periodo: {start_str} → {end_str} ({days} giorni)

## Statistiche

- **Media**: {avg_val:.2f}
- **Minimo**: {min_val:.2f} 
- **Massimo**: {max_val:.2f}
- **Crescita**: {growth_rate:+.2f}% (primo vs ultimo giorno)

## Valori Giornalieri

"""
        
        for date, val in zip(dates, values):
            diff_from_avg = ((val - avg_val) / avg_val * 100) if avg_val > 0 else 0
            report += f"- {date}: {val:.2f} ({diff_from_avg:+.2f}% vs media)\n"
        
        db.close()
        if cache:
            cache.close()
        
        return report
        
    except Exception as e:
        logger.error(f"Errore get_metrics_trend: {e}", exc_info=True)
        return f"❌ Errore analisi trend: {e}"


@tool
def get_weekly_summary() -> str:
    """Get weekly summary comparing current week with previous week.
    
    Compares averages of all metrics between the two weeks.
    
    Returns:
        Formatted string with weekly comparison.
    """
    try:
        db, cache = _get_db_instances()
        
        today = datetime.now()
        
        # Settimana corrente (ultimi 7 giorni)
        current_end = today - timedelta(days=1)
        current_start = current_end - timedelta(days=6)
        
        # Settimana precedente
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=6)
        
        # Query dati
        current_week = db.get_date_range(
            current_start.strftime('%Y-%m-%d'),
            current_end.strftime('%Y-%m-%d')
        )
        
        previous_week = db.get_date_range(
            previous_start.strftime('%Y-%m-%d'),
            previous_end.strftime('%Y-%m-%d')
        )
        
        if not current_week or not previous_week:
            return "❌ Dati insufficienti per confronto settimanale."
        
        # Calcola medie
        def avg_metric(data, metric):
            values = [d[metric] for d in data if metric in d]
            return sum(values) / len(values) if values else 0
        
        def calc_change(current, previous):
            if previous == 0:
                return 0
            return ((current - previous) / previous) * 100
        
        metrics_to_compare = [
            ('sessioni_commodity', 'Sessioni Commodity'),
            ('sessioni_lucegas', 'Sessioni Luce&Gas'),
            ('swi_conversioni', 'Conversioni SWI'),
            ('cr_commodity', 'CR Commodity'),
            ('cr_lucegas', 'CR Luce&Gas'),
        ]
        
        report = f"""# Riepilogo Settimanale

## Settimana Corrente
{current_start.strftime('%d/%m/%Y')} - {current_end.strftime('%d/%m/%Y')} ({len(current_week)} giorni)

## Settimana Precedente
{previous_start.strftime('%d/%m/%Y')} - {previous_end.strftime('%d/%m/%Y')} ({len(previous_week)} giorni)

## Confronto Medie

"""
        
        for metric_key, metric_name in metrics_to_compare:
            curr_avg = avg_metric(current_week, metric_key)
            prev_avg = avg_metric(previous_week, metric_key)
            change = calc_change(curr_avg, prev_avg)
            
            report += f"""**{metric_name}:**
- Settimana corrente: {curr_avg:.2f}
- Settimana precedente: {prev_avg:.2f}
- Variazione: {change:+.2f}%

"""
        
        db.close()
        if cache:
            cache.close()
        
        return report
        
    except Exception as e:
        logger.error(f"Errore get_weekly_summary: {e}", exc_info=True)
        return f"❌ Errore riepilogo settimanale: {e}"