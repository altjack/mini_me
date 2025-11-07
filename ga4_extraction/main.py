import logging
import os
import sys

# Aggiungi il path per gli import
sys.path.insert(0, os.path.dirname(__file__))

from extraction import esegui_giornaliero, save_results_to_csv, create_combined_report

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ga4_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    Funzione principale per eseguire il giornaliero e salvare i risultati
    """
    # Esegui estrazione
    results, dates = esegui_giornaliero(period_type='ieri')
    
    # Salva risultati in CSV
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    
    saved_files = save_results_to_csv(results, output_dir, dates)
    logger.info(f"✓ Salvati {len(saved_files)} file CSV")
    
    # Crea anche report combinato
    combined_file = create_combined_report(results, output_dir, dates)
    logger.info(f"✓ Report combinato creato: {combined_file}")

if __name__ == "__main__":
    main()