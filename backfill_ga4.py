#!/usr/bin/env python3
"""
Script di backfill per database GA4.

Estrae ultimi 60 giorni di dati da GA4 e popola:
- SQLite: tutti i 60 giorni
- Redis: ultimi 14 giorni (cache)

Esegui dopo setup_database.py
"""

import sys
import os
import logging
import yaml
from datetime import datetime, timedelta
from pathlib import Path

# Aggiungi directory corrente al path
sys.path.insert(0, os.path.dirname(__file__))

from ga4_extraction.database import GA4Database
from ga4_extraction.redis_cache import GA4RedisCache
from ga4_extraction.extraction import (
    sessions,
    session_commodity_filter,
    session_lucegas_filter,
    giornaliero_swi,
    calculate_cr,
    giornaliero_prodotti,
    giornaliero_startfunnel,
    giornaliero_cr_canalizzazione,
    daily_sessions_channels,
    client
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backfill_ga4.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config():
    """Carica configurazione da config.yaml."""
    config_path = Path("config.yaml")
    if not config_path.exists():
        raise FileNotFoundError("File config.yaml non trovato")
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def extract_single_day(target_date: datetime) -> dict:
    """
    Estrae dati GA4 per un singolo giorno.
    
    Args:
        target_date: Data da estrarre
    
    Returns:
        Dict con metriche raw
    """
    target_date_str = target_date.strftime('%Y-%m-%d')
    
    # Estrae metriche
    sessioni = sessions(client, target_date_str, session_commodity_filter())
    sessioni_lucegas = sessions(client, target_date_str, session_lucegas_filter())
    swi = giornaliero_swi(client, target_date_str)
    
    # Calcola CR
    cr_commodity = calculate_cr(sessioni, swi)
    cr_lucegas = calculate_cr(sessioni_lucegas, swi)
    
    # Start funnel
    start_funnel_value = giornaliero_startfunnel(client, target_date_str)
    
    # CR Canalizzazione
    cr_can_df = giornaliero_cr_canalizzazione(swi, start_funnel_value)
    
    # Estrai valore CR canalizzazione dal DataFrame
    cr_canalizzazione_value = 0.0
    if cr_can_df is not None and not cr_can_df.empty:
        # Il valore è in formato "XX.XX%", lo convertiamo in float
        cr_can_str = cr_can_df.iloc[0]['Value']
        cr_canalizzazione_value = float(cr_can_str.replace('%', ''))
    
    # Prodotti
    prodotti_df = giornaliero_prodotti(client, target_date_str, swi)
    
    # Converti prodotti DataFrame in lista di dict
    products = []
    if prodotti_df is not None and not prodotti_df.empty:
        for _, row in prodotti_df.iterrows():
            # Rimuovi % dal percentage
            percentage_str = row['Percentage'].replace('%', '')
            products.append({
                'product_name': row['Product'],
                'total_conversions': float(row['Total']),
                'percentage': float(percentage_str)
            })
    
    # Sessioni per canale
    sessioni_canale_df = daily_sessions_channels(client, target_date_str)
    
    # Converti sessioni per canale DataFrame in lista di dict
    channels = []
    if sessioni_canale_df is not None and not sessioni_canale_df.empty:
        for _, row in sessioni_canale_df.iterrows():
            channels.append({
                'channel': row['Channel'],
                'commodity_sessions': int(row['Commodity_Sessions']),
                'lucegas_sessions': int(row['LuceGas_Sessions'])
            })
    
    # Ritorna valori RAW
    return {
        'sessioni_commodity': sessioni,
        'sessioni_lucegas': sessioni_lucegas,
        'swi_conversioni': swi,
        'cr_commodity': cr_commodity,
        'cr_lucegas': cr_lucegas,
        'cr_canalizzazione': cr_canalizzazione_value,
        'start_funnel': int(start_funnel_value),
        'products': products,
        'channels': channels
    }


def main():
    """Backfill principale."""
    
    print("=" * 80)
    print("  📊 BACKFILL DATABASE GA4")
    print("=" * 80)
    print()
    print("⚠️  NOTA: I dati di traffico e canali impiegano ~48h ad essere processati da GA4")
    print("   Il backfill estrae da 'ieri - N giorni' a 'ieri - 1' (esclude ieri stesso)")
    print()
    
    # Carica config
    try:
        config = load_config()
        backfill_days = config.get('ga4_extraction', {}).get('backfill_days', 60)
        db_config = config.get('database', {})
        
        print(f"⚙️  Configurazione caricata")
        print(f"   Giorni da estrarre: {backfill_days}")
        print()
        
    except Exception as e:
        print(f"❌ Errore caricamento config: {e}")
        return 1
    
    # Setup database
    try:
        db_path = db_config.get('sqlite', {}).get('path', 'data/ga4_data.db')
        db = GA4Database(db_path)
        print(f"✓ Database SQLite connesso: {db_path}")
        
        # Verifica schema
        stats = db.get_statistics()
        if stats['record_count'] > 0:
            print(f"⚠️  Database contiene già {stats['record_count']} record")
            response = input("   Continuare con backfill? (sovrascrivi record esistenti) [y/N]: ")
            if response.lower() != 'y':
                print("Backfill annullato")
                return 0
        
    except Exception as e:
        print(f"❌ Errore setup database: {e}")
        logger.error(f"Errore setup database: {e}", exc_info=True)
        return 1
    
    # Setup Redis (opzionale)
    try:
        redis_config = db_config.get('redis', {})
        cache = GA4RedisCache(
            host=redis_config.get('host', 'localhost'),
            port=redis_config.get('port', 6379),
            db=redis_config.get('db', 1),
            key_prefix=redis_config.get('key_prefix', 'ga4:metrics:'),
            ttl_days=redis_config.get('ttl_days', 14)
        )
        print(f"✓ Redis cache connesso")
        redis_enabled = True
    except Exception as e:
        print(f"⚠️  Redis non disponibile: {e}")
        print(f"   Continuo solo con SQLite...")
        redis_enabled = False
    
    print()
    print("=" * 80)
    print("  🚀 INIZIO ESTRAZIONE")
    print("=" * 80)
    print()
    
    # Calcola date
    # IMPORTANTE: I dati di traffico e canali impiegano ~48h ad essere processati da GA4
    # Quindi estraiamo da "ieri - backfill_days" a "ieri - 1" (escludiamo ieri stesso)
    today = datetime.now()
    ieri = today - timedelta(days=1)
    start_date = ieri - timedelta(days=backfill_days)  # Data più vecchia
    end_date = ieri - timedelta(days=1)  # Data più recente (ieri - 1)
    
    print(f"📅 Range estrazione:")
    print(f"   Data più vecchia: {start_date.strftime('%Y-%m-%d')}")
    print(f"   Data più recente: {end_date.strftime('%Y-%m-%d')}")
    print(f"   (Esclusi: {ieri.strftime('%Y-%m-%d')} e {today.strftime('%Y-%m-%d')})")
    print()
    
    success_count = 0
    error_count = 0
    
    # Estrai dal più vecchio al più recente
    for i in range(backfill_days):
        target_date = start_date + timedelta(days=i)
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        try:
            print(f"[{i + 1}/{backfill_days}] Estrazione {target_date_str}...", end=' ', flush=True)
            
            # Estrai dati
            metrics = extract_single_day(target_date)
            
            # Salva in SQLite
            db.insert_daily_metrics(target_date_str, metrics, replace=True)
            db.insert_products(target_date_str, metrics['products'], replace=True)
            db.insert_sessions_by_channel(target_date_str, metrics['channels'], replace=True)
            
            # Salva in Redis (solo ultimi 14 giorni del range)
            if redis_enabled and i >= backfill_days - 14:
                cache_metrics = {k: v for k, v in metrics.items() if k not in ['products', 'channels']}
                cache.set_metrics(target_date_str, cache_metrics)
            
            print(f"✓ OK ({metrics['swi_conversioni']} conv, {len(metrics['products'])} prod, {len(metrics['channels'])} canali)")
            success_count += 1
            
        except Exception as e:
            print(f"✗ ERRORE: {e}")
            logger.error(f"Errore estrazione {target_date_str}: {e}", exc_info=True)
            error_count += 1
            
            # Se troppi errori consecutivi, interrompi
            if error_count > 5:
                print()
                print("❌ Troppi errori consecutivi. Interrompo backfill.")
                break
    
    print()
    print("=" * 80)
    print("  📊 RIEPILOGO BACKFILL")
    print("=" * 80)
    print()
    
    # Statistiche finali
    stats = db.get_statistics()
    
    print(f"  ✓ Giorni estratti con successo: {success_count}/{backfill_days}")
    print(f"  ✗ Errori: {error_count}")
    print()
    print(f"  📅 Periodo coperto: {stats['min_date']} → {stats['max_date']}")
    print(f"  📊 Record totali in DB: {stats['record_count']}")
    print(f"  📈 Media sessioni commodity: {stats['avg_sessioni_commodity']:.0f}")
    print(f"  📈 Media conversioni SWI: {stats['avg_swi_conversioni']:.0f}")
    print()
    
    if redis_enabled:
        cache_info = cache.get_cache_info()
        print(f"  💾 Redis cache popolato: {cache_info['cached_days']} giorni")
        print()
    
    if success_count == backfill_days:
        print("  ✅ BACKFILL COMPLETATO CON SUCCESSO!")
    elif success_count > 0:
        print("  ⚠️  BACKFILL PARZIALMENTE COMPLETATO")
    else:
        print("  ❌ BACKFILL FALLITO")
    
    print()
    print("  📝 PROSSIMI PASSI:")
    print()
    print("  1. Esegui workflow giornaliero:")
    print("     python main.py")
    print()
    print("  2. Testa agente con nuovo database:")
    print("     python run_agent.py")
    print()
    
    # Cleanup
    db.close()
    if redis_enabled:
        cache.close()
    
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Backfill interrotto dall'utente")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Errore imprevisto: {e}")
        logger.error(f"Errore imprevisto: {e}", exc_info=True)
        sys.exit(1)

