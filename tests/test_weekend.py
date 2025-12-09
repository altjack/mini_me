import unittest
import sys
import os
from datetime import datetime, timedelta

#Aggiungi path progetto
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.tools import get_weekend_report
from ga4_extraction.database import GA4Database
from ga4_extraction.factory import GA4ResourceFactory

class TestWeekend(unittest.TestCase):

    def setUp(self):
        """Setup environment for testing"""
        self.config = {
            "database": {
                "sqlite": {'path': 'data/ga4_data.db'}
            }
        }
    
    def test_weekend_logic(self):
        """Testa la generazione del report weeekend simulando che sia lunedì 17/11/2025
        Il test dovrebbe coprire le date venerdì 14/11/2025, sabato 15/11/2025 e domenica 16/11/2025"""

        mock_today = "2025-11-17" # Lunedì

        print(f"Testing weekend report logic for {mock_today}")

        #esegui il tool
        report = get_weekend_report(reference_date=mock_today)

        print("\n--- Report generated: ---")
        print(report)
        print("\n--- End of report ---")

        #Verifiche
        self.assertIsInstance(report, str)
        self.assertIn("Recap Weekend", report)
        
        #Verifica le date presenti (formato italiano da tool)
        self.assertIn("Venerdì 14", report)
        self.assertIn("Sabato 15", report)
        self.assertIn("Domenica 16", report)

        if "Dati mancanti" not in report:
            self.assertIn("Totale weekend", report)
            self.assertIn("SWI Totali", report)

if __name__ == "__main__":
    unittest.main()