"""Tool functions for the agent to interact with GA4 extraction module."""

from atexit import register
import sys
import os
import logging
import glob
import yaml
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional
import pandas
from datapizza.tools import tool

from backend.ga4_extraction.extraction import (
    esegui_giornaliero,
    calculate_dates,
    save_results_to_csv,
    create_combined_report
)
from backend.ga4_extraction.database import GA4Database
from backend.ga4_extraction.redis_cache import GA4RedisCache
from backend.agent.session import get_connections

# Configurazione del logger - usa /tmp su Vercel/Lambda (filesystem read-only)
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

# Cache in-process per evitare chiamate duplicate sullo stesso giorno
_daily_report_cache: Dict[Tuple[str, int], str] = {}


def format_dataframe(df: pandas.DataFrame, section_name: str = "", max_rows: int = 20) -> str:
    """
    Converte un DataFrame pandas in una tabella Markdown leggibile.

    Args:
        df: DataFrame da formattare.
        section_name: Nome sezione (non utilizzato ma mantenuto per retrocompatibilità).
        max_rows: Numero massimo di righe da includere per evitare output eccessivo.

    Returns:
        Stringa Markdown rappresentante il DataFrame.
    """
    if df is None or df.empty:
        return ""

    try:
        df_to_use = df.head(max_rows).copy()
        df_to_use = df_to_use.fillna(0)
        return df_to_use.to_markdown(index=False)
    except Exception as exc:  # pragma: no cover
        logger.warning(f"Impossibile formattare DataFrame '{section_name}': {exc}")
        return df.to_string(index=False)


def _generate_daily_report_content(
    target_date: datetime,
    compare_days_ago: int = 7,
    header_template: Optional[str] = None,
) -> str:
    """
    Genera il contenuto testuale del report giornaliero partendo da una data target.

    Args:
        target_date: Data target come oggetto datetime.
        compare_days_ago: Giorni da utilizzare per il confronto storico.
        header_template: Template personalizzato per l'header del report.

    Returns:
        Stringa formattata contenente il report completo.
    """
    target_date_str = target_date.strftime('%Y-%m-%d')
    db, cache, should_close = get_connections()

    try:
        current = db.get_metrics(target_date_str)
        if not current:
            return f"❌ Nessun dato disponibile per {target_date_str}"

        comparison = db.calculate_comparison(target_date_str, days_ago=compare_days_ago)
        prev: Dict[str, Any] = {}
        comp_info: Dict[str, Any] = {}

        if comparison and comparison.get('previous'):
            prev = comparison.get('previous', {}) or {}
            comp_info = comparison.get('comparison', {}) or {}
            prev_info = f"Confrontato con: {comparison['previous_date']}"
        else:
            prev_info = "Nessun dato di confronto disponibile"

        giorni_settimana = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']
        mesi = [
            'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
            'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'
        ]
        giorno_nome = giorni_settimana[target_date.weekday()]
        mese_nome = mesi[target_date.month - 1]
        data_formattata = f"{giorno_nome.capitalize()} {target_date.day} {mese_nome}"

        header_template = header_template or (
            "# Report Giornaliero GA4 - {data_formattata} ({target_date})\n"
            "{prev_info}\n"
            "### Generato il: {generated_at}"
        )

        header = header_template.format(
            data_formattata=data_formattata,
            target_date=target_date_str,
            prev_info=prev_info,
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )

        lines = [
            header,
            "",
            "## Sessioni",
            "",
            "**Commodity:**",
            f"- Corrente: {current['sessioni_commodity']:,}",
        ]

        if prev:
            lines.append(f"- Precedente: {prev.get('sessioni_commodity', 0):,}")
        if comp_info:
            lines.append(f"- Variazione: {comp_info.get('sessioni_commodity_change', 0):+.2f}%")

        lines.extend([
            "",
            "**Luce&Gas:**",
            f"- Corrente: {current['sessioni_lucegas']:,}",
        ])

        if prev:
            lines.append(f"- Precedente: {prev.get('sessioni_lucegas', 0):,}")
        if comp_info:
            lines.append(f"- Variazione: {comp_info.get('sessioni_lucegas_change', 0):+.2f}%")

        lines.extend([
            "",
            "## Conversioni",
            "",
            "**SWI (Switch In):**",
            f"- Corrente: {current['swi_conversioni']:,}",
        ])

        if prev:
            lines.append(f"- Precedente: {prev.get('swi_conversioni', 0):,}")
        if comp_info:
            lines.append(f"- Variazione: {comp_info.get('swi_conversioni_change', 0):+.2f}%")

        lines.extend([
            "",
            "## Conversion Rates",
            "",
            "**CR Commodity:**",
            f"- Corrente: {current['cr_commodity']:.2f}%",
        ])

        if prev:
            lines.append(f"- Precedente: {prev.get('cr_commodity', 0):.2f}%")
        if comp_info:
            lines.append(f"- Variazione: {comp_info.get('cr_commodity_change', 0):+.2f}%")

        lines.extend([
            "",
            "**CR Luce&Gas:**",
            f"- Corrente: {current['cr_lucegas']:.2f}%",
        ])

        if prev:
            lines.append(f"- Precedente: {prev.get('cr_lucegas', 0):.2f}%")
        if comp_info:
            lines.append(f"- Variazione: {comp_info.get('cr_lucegas_change', 0):+.2f}%")

        lines.extend([
            "",
            "**CR Canalizzazione:**",
            f"- Corrente: {current['cr_canalizzazione']:.2f}%",
            "",
            "**Start Funnel:**",
            f"- Corrente: {current['start_funnel']:,}",
        ])

        products = db.get_products(target_date_str)
        if products:
            lines.extend([
                "",
                "## Performance Prodotti",
                "",
            ])
            for prod in products:
                lines.append(
                    f"- **{prod['product_name'].capitalize()}**: "
                    f"{int(prod['total_conversions'])} conversioni ({prod['percentage']:.2f}%)"
                )

        channels = db.get_sessions_by_channel(target_date_str)
        if channels:
            lines.extend([
                "",
                "## Sessioni per Canale",
                "",
            ])
            for ch in channels:
                lines.append(
                    f"- **{ch['channel']}**: {ch['commodity_sessions']:,} commodity, "
                    f"{ch['lucegas_sessions']:,} luce&gas"
                )

        return "\n".join(lines)

    finally:
        if should_close:
            db.close()
            if cache:
                cache.close()


@tool
def get_daily_report(date: Optional[str] = None, compare_days_ago: int = 7) -> str:
    """Get the daily report for a given date from database.

    Args:
        date: Data nel formato YYYY-MM-DD. Se non fornita, usa la data di ieri.
        compare_days_ago: Giorni da utilizzare per il confronto (default: 7).

    Returns:
        Stringa formattata contenente il report giornaliero.
    """
    # #region agent log
    import json as _json; _log_path = "/Users/giacomomauri/Desktop/Automation/daily_report/.cursor/debug.log"
    def _debug_log(loc, msg, data, hyp): open(_log_path, "a").write(_json.dumps({"location": loc, "message": msg, "data": data, "hypothesisId": hyp, "timestamp": __import__("time").time()}) + "\n")
    _debug_log("tools.py:get_daily_report", "Tool called", {"date": date, "compare_days_ago": compare_days_ago}, "D")
    # #endregion
    try:
        if date:
            target_date = datetime.strptime(date, '%Y-%m-%d')
        else:
            target_date = datetime.now() - timedelta(days=1)

        # Normalizza a mezzanotte per coerenza e cache
        target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        target_date_str = target_date.strftime('%Y-%m-%d')
        cache_key = (target_date_str, compare_days_ago)

        if cache_key in _daily_report_cache:
            logger.info(f"get_daily_report cache hit per {cache_key}")
            # #region agent log
            _debug_log("tools.py:get_daily_report", "Cache hit", {"target_date": target_date_str}, "D")
            # #endregion
            return _daily_report_cache[cache_key]

        result = _generate_daily_report_content(target_date, compare_days_ago=compare_days_ago)
        _daily_report_cache[cache_key] = result
        # #region agent log
        _debug_log("tools.py:get_daily_report", "Tool success", {"result_len": len(result), "result_preview": result[:200]}, "D")
        # #endregion
        return result

    except Exception as e:
        logger.error(f"Errore nella generazione del report giornaliero: {e}", exc_info=True)
        # #region agent log
        _debug_log("tools.py:get_daily_report", "Tool FAILED", {"error": str(e)}, "D")
        # #endregion
        return f"Errore nella generazione del report giornaliero: {e}"

@tool
def get_weekend_report(reference_date: Optional[str] = None) -> str:
    """Create a report for the weekend days (Friday, Saturday and Sunday) comparing each day with the previous week.
    
    Args:
        reference_date: Optional date in YYYY-MM-DD format. If not provided, uses today's date.
    
    Returns:
        Formatted string containing the weekend report.
    """
    try:
        if reference_date:
            ref_date = datetime.strptime(reference_date, '%Y-%m-%d')
        else:
            ref_date = datetime.now()
        
        #Verify that is monday
        if ref_date.weekday() != 0: #0 is monday
            logger.warning(f"Function called in a date different from monday")
        
        days=[]
        #Get them in chronological order
        for offset in [3,2,1]:
            day_dt = ref_date - timedelta(days = offset)
            days.append(day_dt)
        
        report = f"# Recap Weekend ({days[0].strftime('%d/%m')} - {days[2].strftime('%d/%m')})\n\n"

        db, _, should_close = get_connections()
        try:
            total_sess_comm = 0
            total_sess_lucegas = 0
            total_swi = 0

            for day in days:
                days_str = day.strftime('%Y-%m-%d')
                metrics = db.get_metrics(days_str)

                # Translate day name
                giorno_nome = day.strftime('%A')
                map_giorni = {
                    'Monday': 'Lunedì', 'Tuesday': 'Martedì', 'Wednesday': 'Mercoledì',
                    'Thursday': 'Giovedì', 'Friday': 'Venerdì', 'Saturday': 'Sabato', 'Sunday': 'Domenica'
                }
                nome_it = map_giorni.get(giorno_nome, giorno_nome)
                
                # Format header like: ### Venerdì 14 November
                # Note: Month might still be English if we don't translate it, but test only checks Day Name + Day Number
                report += f"### {nome_it} {day.day}\n"

                if not metrics:
                    report += "❌ Dati mancanti\n\n"
                    continue
                
                #Calculate comparison (day - 7)
                comp = db.calculate_comparison(days_str, days_ago = 7)

                #Extract key metrics variations
                swi_change = comp['comparison'].get('swi_conversioni_change',0)
                sess_comm_change = comp['comparison'].get('sessioni_commodity_change',0)
                sess_lucegas_change = comp['comparison'].get('sessioni_lucegas_change',0)
                cr_comm_change = comp['comparison'].get('cr_commodity_change',0)
                cr_lucegas_change = comp['comparison'].get('cr_lucegas_change',0)

                #Accumulate totals
                total_sess_comm += metrics['sessioni_commodity']
                total_sess_lucegas += metrics['sessioni_lucegas']
                total_swi += metrics['swi_conversioni']


                #Format report for each day
                report += f"**SWI:** {metrics['swi_conversioni']} ({swi_change:+.2f}% vs sett.prec.)\n"
                report += f"**Sessioni Commodity:** {metrics['sessioni_commodity']:,} ({sess_comm_change:+.2f}% vs sett.prec.)\n"
                report += f"**Sessioni Luce&Gas:** {metrics['sessioni_lucegas']:,} ({sess_lucegas_change:+.2f}% vs sett.prec.)\n"
                report += f"**CR Commodity:** {metrics['cr_commodity']:.2f}% ({cr_comm_change:+.2f}% vs sett.prec.)\n"
                report += f"**CR Luce&Gas:** {metrics['cr_lucegas']:.2f}% ({cr_lucegas_change:+.2f}% vs sett.prec.)\n"
                
            # Calcola CR totali dai totali accumulati
            total_cr_comm = (total_swi / total_sess_comm * 100) if total_sess_comm > 0 else 0
            total_cr_lucegas = (total_swi / total_sess_lucegas * 100) if total_sess_lucegas > 0 else 0
            
            report += "### Totale weekend\n"
            report += f"**SWI Totali** :  {total_swi:,} | **Sessioni Commodity Totali**: {total_sess_comm:,} | **Sessioni Luce&Gas Totali**: {total_sess_lucegas:,} | **CR Commodity Totali**: {total_cr_comm:.2f}% | **CR Luce&Gas Totali**: {total_cr_lucegas:.2f}%\n"
            return report

        finally:
            if should_close:
                db.close()

    except Exception as e:
        logger.error(f"Errore nella generazione del report weekend: {e}", exc_info=True)
        return f"Errore nella generazione del report weekend: {e}"

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
        
        db, cache, should_close = get_connections()
        
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
        
        if should_close:
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
    # Path al config.yaml nella root del progetto
    # Da backend/agent/tools.py -> ../../config.yaml
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.yaml')

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
            ttl_days=redis_config.get('ttl_days', 21)
        )
    except Exception as e:
        logger.warning(f"Redis non disponibile: {e}")
        cache = None

    return db, cache


# ============================================================================
# PROMO CALENDAR TOOLS
# ============================================================================

def _load_promo_calendar() -> pandas.DataFrame:
    """
    Helper per caricare il calendario promozioni da JSON.

    Returns:
        DataFrame con calendario promozioni

    Raises:
        FileNotFoundError: Se file non trovato
    """
    import json
    
    # Path al file JSON in src/data/ (relativo alla root del progetto)
    # Da backend/agent/tools.py -> ../../src/data/promoCalendar.json
    promo_path = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'data', 'promoCalendar.json')

    if not os.path.exists(promo_path):
        raise FileNotFoundError(f"File calendario promozioni non trovato: {promo_path}")

    with open(promo_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Converti in DataFrame
    df = pandas.DataFrame(data['promos'])
    
    # Rinomina colonne per compatibilità con il codice esistente
    df = df.rename(columns={
        'name': 'nome_promo',
        'type': 'Tipoologia',
        'startDate': 'data_inizio',
        'endDate': 'data_fine',
        'product': 'prodotto',
        'contractType': 'tipologia_contratto',
        'conditions': 'condizioni'
    })

    # Convert date columns to datetime and normalize to date only (no time)
    df['data_inizio'] = pandas.to_datetime(df['data_inizio']).dt.normalize()
    df['data_fine'] = pandas.to_datetime(df['data_fine']).dt.normalize()

    return df


def _find_promo_for_comparison(target_date: datetime, lookback_min: int = 7, lookback_max: int = 21) -> Optional[dict]:
    """
    Trova una promo attiva nello stesso giorno della settimana negli ultimi 7-21 giorni.

    Args:
        target_date: Data target per cui cercare promo da confrontare
        lookback_min: Giorni minimi da guardare indietro (default: 7)
        lookback_max: Giorni massimi da guardare indietro (default: 21)

    Returns:
        Dict con info promo trovata o None
    """
    try:
        df = _load_promo_calendar()

        # Normalize target_date to midnight for consistent comparison
        target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        target_weekday = target_date.weekday()  # 0 = Monday, 6 = Sunday

        # Cerca nei giorni precedenti con stesso giorno settimana
        for days_back in range(lookback_min, lookback_max + 1):
            compare_date = target_date - timedelta(days=days_back)
            # Normalize to midnight
            compare_date = compare_date.replace(hour=0, minute=0, second=0, microsecond=0)

            # Check se stesso giorno della settimana
            if compare_date.weekday() != target_weekday:
                continue

            # Cerca promo attiva in quella data
            active_promos = df[
                (df['data_inizio'] <= compare_date) &
                (df['data_fine'] >= compare_date)
            ]

            if not active_promos.empty:
                # Prendi la prima promo trovata (se più di una, priorità alla prima nel CSV)
                promo = active_promos.iloc[0]

                return {
                    'date': compare_date.strftime('%Y-%m-%d'),
                    'weekday': compare_date.strftime('%A'),
                    'nome_promo': promo['nome_promo'],
                    'tipologia': promo['Tipoologia'],  # Note: typo in CSV column name
                    'prodotto': promo['prodotto'],
                    'contratto': promo['tipologia_contratto'],
                    'condizioni': promo['condizioni'],
                    'days_back': days_back
                }

        return None

    except Exception as e:
        logger.error(f"Errore ricerca promo per confronto: {e}", exc_info=True)
        return None


@tool
def get_active_promos(date: Optional[str] = None) -> str:
    """Get active promotions for a specific date and suggest comparison with past promos.

    This tool:
    1. Finds all promotions active on the target date
    2. Searches for promotions active on the same weekday in the past 7-21 days
    3. Suggests comparison between current and past promo periods

    Args:
        date: Date in YYYY-MM-DD format. If not provided, uses yesterday's date.

    Returns:
        Formatted string with:
        - Active promotions for the target date
        - Past promotions for comparison (if found)
        - Suggestion to use compare_promo_periods() for detailed analysis
    """
    # #region agent log
    import json as _json; _log_path = "/Users/giacomomauri/Desktop/Automation/daily_report/.cursor/debug.log"
    def _debug_log(loc, msg, data, hyp): open(_log_path, "a").write(_json.dumps({"location": loc, "message": msg, "data": data, "hypothesisId": hyp, "timestamp": __import__("time").time()}) + "\n")
    _debug_log("tools.py:get_active_promos", "Tool called", {"date": date}, "D")
    # #endregion
    try:
        # Parse target date and normalize to date only (no time component)
        if date:
            target_date = datetime.strptime(date, '%Y-%m-%d')
        else:
            target_date = datetime.now() - timedelta(days=1)

        # Normalize to midnight (00:00:00) for consistent comparison
        target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)

        # Load promo calendar
        df = _load_promo_calendar()

        # Filter active promos for target date
        active = df[
            (df['data_inizio'] <= target_date) &
            (df['data_fine'] >= target_date)
        ]

        # Format weekday in Italian
        giorni_settimana = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
        giorno_nome = giorni_settimana[target_date.weekday()]

        report = f"# Promozioni Attive - {giorno_nome} {target_date.strftime('%d/%m/%Y')}\n\n"

        if active.empty:
            report += "❌ **Nessuna promozione attiva in questa data**\n\n"
        else:
            report += "## ✅ Promozioni Correnti\n\n"

            for _, promo in active.iterrows():
                start = promo['data_inizio'].strftime('%d/%m/%Y')
                end = promo['data_fine'].strftime('%d/%m/%Y')

                # Distingui Promo da Prodotto
                tipo_badge = "🎯 PROMO" if promo['Tipoologia'] == 'Promo' else "📦 PRODOTTO"

                report += f"### {tipo_badge}: {promo['nome_promo']}\n"
                report += f"- **Periodo**: {start} - {end}\n"
                report += f"- **Prodotto**: {promo['prodotto']}\n"
                report += f"- **Contratto**: {promo['tipologia_contratto']}\n"
                report += f"- **Condizioni**: {promo['condizioni']}\n\n"

        # Search for promo on same weekday in past 7-21 days
        past_promo = _find_promo_for_comparison(target_date)

        if past_promo:
            report += "---\n\n"
            report += "## 📊 Confronto con Promo Precedente Disponibile\n\n"

            # Traduci weekday
            weekday_map = {
                'Monday': 'Lunedì', 'Tuesday': 'Martedì', 'Wednesday': 'Mercoledì',
                'Thursday': 'Giovedì', 'Friday': 'Venerdì', 'Saturday': 'Sabato', 'Sunday': 'Domenica'
            }
            past_weekday = weekday_map.get(past_promo['weekday'], past_promo['weekday'])

            tipo_badge_past = "🎯 PROMO" if past_promo['tipologia'] == 'Promo' else "📦 PRODOTTO"

            report += f"Trovata promo attiva **{past_promo['days_back']} giorni fa** ({past_promo['date']}, {past_weekday}):\n\n"
            report += f"### {tipo_badge_past}: {past_promo['nome_promo']}\n"
            report += f"- **Prodotto**: {past_promo['prodotto']}\n"
            report += f"- **Contratto**: {past_promo['contratto']}\n"
            report += f"- **Condizioni**: {past_promo['condizioni']}\n\n"

            report += "💡 **Suggerimento**: Usa `compare_promo_periods()` per confrontare:\n"
            report += f"   - {giorno_nome} {target_date.strftime('%d/%m')} (oggi)\n"
            report += f"   - {past_weekday} {datetime.strptime(past_promo['date'], '%Y-%m-%d').strftime('%d/%m')} ({past_promo['days_back']} giorni fa)\n"
            report += f"   - Metriche confrontate: SWI, CR Commodity, CR L&G, Sessioni\n"
        else:
            report += "---\n\n"
            report += "ℹ️ **Nessuna promo precedente** trovata nello stesso giorno della settimana (ultimi 7-21 giorni)\n"

        # #region agent log
        _debug_log("tools.py:get_active_promos", "Tool success", {"result_len": len(report)}, "D")
        # #endregion
        return report

    except Exception as e:
        logger.error(f"Errore nel recupero promozioni attive: {e}", exc_info=True)
        # #region agent log
        _debug_log("tools.py:get_active_promos", "Tool FAILED", {"error": str(e)}, "D")
        # #endregion
        return f"❌ Errore nel recupero promozioni: {e}"


@tool
def compare_promo_periods(current_date: str, compare_date: str) -> str:
    """Compare metrics between two dates with different active promotions.

    This tool provides a detailed side-by-side comparison of key metrics
    (SWI, CR, Sessions) between two promotional periods.

    Args:
        current_date: First date in YYYY-MM-DD format (typically the recent date).
        compare_date: Second date in YYYY-MM-DD format (typically the past date).

    Returns:
        Formatted string with:
        - Promotions active on both dates
        - Side-by-side metrics comparison (SWI, CR Commodity, CR L&G, Sessions)
        - Percentage variations between the two periods
    """
    try:
        # Parse dates and normalize to midnight for consistent comparison
        date1 = datetime.strptime(current_date, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)
        date2 = datetime.strptime(compare_date, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)

        # Load promo calendar
        df = _load_promo_calendar()

        # Find promos for both dates
        promos1 = df[(df['data_inizio'] <= date1) & (df['data_fine'] >= date1)]
        promos2 = df[(df['data_inizio'] <= date2) & (df['data_fine'] >= date2)]

        # Get metrics from database
        db, _, should_close = get_connections()

        try:
            metrics1 = db.get_metrics(current_date)
            metrics2 = db.get_metrics(compare_date)

            if not metrics1 or not metrics2:
                return f"❌ Dati mancanti per una o entrambe le date: {current_date}, {compare_date}"

            # Format weekdays
            giorni_settimana = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
            giorno1 = giorni_settimana[date1.weekday()]
            giorno2 = giorni_settimana[date2.weekday()]

            # Build report
            report = f"# Confronto Periodi con Promo Diverse\n\n"

            # Section 1: Periodo 1 (current)
            report += f"## 📅 Periodo 1: {giorno1} {date1.strftime('%d/%m/%Y')}\n\n"

            if promos1.empty:
                report += "❌ **Nessuna promozione attiva**\n\n"
            else:
                for _, promo in promos1.iterrows():
                    tipo_badge = "🎯 PROMO" if promo['Tipoologia'] == 'Promo' else "📦 PRODOTTO"
                    report += f"**{tipo_badge}: {promo['nome_promo']}**\n"
                    report += f"- Prodotto: {promo['prodotto']} ({promo['tipologia_contratto']})\n"
                    report += f"- Condizioni: {promo['condizioni']}\n\n"

            # Section 2: Periodo 2 (compare)
            report += f"## 📅 Periodo 2: {giorno2} {date2.strftime('%d/%m/%Y')}\n\n"

            if promos2.empty:
                report += "❌ **Nessuna promozione attiva**\n\n"
            else:
                for _, promo in promos2.iterrows():
                    tipo_badge = "🎯 PROMO" if promo['Tipoologia'] == 'Promo' else "📦 PRODOTTO"
                    report += f"**{tipo_badge}: {promo['nome_promo']}**\n"
                    report += f"- Prodotto: {promo['prodotto']} ({promo['tipologia_contratto']})\n"
                    report += f"- Condizioni: {promo['condizioni']}\n\n"

            # Section 3: Metrics comparison
            report += "---\n\n"
            report += "## 📊 Confronto Metriche Chiave\n\n"

            # Helper function for variation
            def calc_var(val1, val2):
                if val2 == 0:
                    return 0.0
                return ((val1 - val2) / val2) * 100

            # SWI Conversioni
            swi_var = calc_var(metrics1['swi_conversioni'], metrics2['swi_conversioni'])
            report += f"### SWI Conversioni\n"
            report += f"- **{giorno1}**: {metrics1['swi_conversioni']:,}\n"
            report += f"- **{giorno2}**: {metrics2['swi_conversioni']:,}\n"
            report += f"- **Variazione**: {swi_var:+.2f}%\n\n"

            # CR Commodity
            cr_comm_var = calc_var(metrics1['cr_commodity'], metrics2['cr_commodity'])
            report += f"### CR Commodity\n"
            report += f"- **{giorno1}**: {metrics1['cr_commodity']:.2f}%\n"
            report += f"- **{giorno2}**: {metrics2['cr_commodity']:.2f}%\n"
            report += f"- **Variazione**: {cr_comm_var:+.2f}%\n\n"

            # CR Luce&Gas
            cr_lg_var = calc_var(metrics1['cr_lucegas'], metrics2['cr_lucegas'])
            report += f"### CR Luce&Gas\n"
            report += f"- **{giorno1}**: {metrics1['cr_lucegas']:.2f}%\n"
            report += f"- **{giorno2}**: {metrics2['cr_lucegas']:.2f}%\n"
            report += f"- **Variazione**: {cr_lg_var:+.2f}%\n\n"

            # Sessioni Commodity
            sess_comm_var = calc_var(metrics1['sessioni_commodity'], metrics2['sessioni_commodity'])
            report += f"### Sessioni Commodity\n"
            report += f"- **{giorno1}**: {metrics1['sessioni_commodity']:,}\n"
            report += f"- **{giorno2}**: {metrics2['sessioni_commodity']:,}\n"
            report += f"- **Variazione**: {sess_comm_var:+.2f}%\n\n"

            # Sessioni Luce&Gas
            sess_lg_var = calc_var(metrics1['sessioni_lucegas'], metrics2['sessioni_lucegas'])
            report += f"### Sessioni Luce&Gas\n"
            report += f"- **{giorno1}**: {metrics1['sessioni_lucegas']:,}\n"
            report += f"- **{giorno2}**: {metrics2['sessioni_lucegas']:,}\n"
            report += f"- **Variazione**: {sess_lg_var:+.2f}%\n\n"

            # Summary insight
            report += "---\n\n"
            report += "💡 **Insight**: "

            if swi_var > 10:
                report += f"Il periodo 1 mostra un **incremento significativo** delle conversioni SWI ({swi_var:+.2f}%), "
            elif swi_var < -10:
                report += f"Il periodo 1 mostra un **decremento significativo** delle conversioni SWI ({swi_var:+.2f}%), "
            else:
                report += f"Le conversioni SWI sono **stabili** tra i due periodi ({swi_var:+.2f}%), "

            if not promos1.empty and not promos2.empty:
                report += f"nonostante entrambi i periodi avessero promozioni attive. "
                report += f"Questo suggerisce differenze nell'efficacia delle campagne o nel contesto di mercato."
            elif not promos1.empty and promos2.empty:
                report += f"probabilmente grazie all'attivazione della promozione nel periodo 1."
            elif promos1.empty and not promos2.empty:
                report += f"nonostante il periodo 2 avesse una promozione attiva (possibile effetto saturazione)."
            else:
                report += f"in assenza di promozioni attive in entrambi i periodi."

            return report

        finally:
            if should_close:
                db.close()

    except Exception as e:
        logger.error(f"Errore nel confronto periodi promo: {e}", exc_info=True)
        return f"❌ Errore nel confronto periodi promo: {e}"