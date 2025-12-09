"""
Approval step implementation.

Handles draft approval with:
- Interactive CLI or automatic approval
- Archive to history
- Add to Redis memory
- Update history.md
"""

import os
import shutil
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from workflows.result_types import ApprovalResult, StepStatus


class ApprovalStep:
    """
    Implementazione step approvazione.
    
    Gestisce:
    - Approvazione interattiva (CLI) o automatica (API)
    - Archiviazione draft approvati
    - Aggiornamento history.md (formato compatibile con examples.py)
    - Aggiunta a memoria Redis (per few-shot learning)
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        logger: Optional[logging.Logger] = None
    ):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
    
    def execute(
        self,
        interactive: bool = True
    ) -> ApprovalResult:
        """
        Esegue approvazione draft.
        
        Args:
            interactive: Se True, chiede conferma utente
            
        Returns:
            ApprovalResult con esito operazione
        """
        try:
            draft_path = self._get_draft_path()
            
            # Verifica esistenza draft
            if not os.path.exists(draft_path):
                return ApprovalResult(
                    status=StepStatus.FAILED,
                    message="Nessun draft da approvare",
                    error=f"File non trovato: {draft_path}"
                )
            
            # Leggi contenuto
            with open(draft_path, 'r', encoding='utf-8') as f:
                full_content = f.read()
            
            # Estrai contenuto email (rimuovi header metadata)
            email_content = self._extract_email_content(full_content)
            
            # Approvazione interattiva
            if interactive:
                approved = self._interactive_approval(email_content)
                if not approved:
                    return ApprovalResult(
                        status=StepStatus.FAILED,
                        message="Draft rifiutato dall'utente"
                    )
            
            # Archivia
            archive_path = self._archive_draft(draft_path)
            
            # Aggiungi a Redis Memory
            memory_added = self._add_to_redis_memory(email_content)
            
            # Aggiorna history.md (formato compatibile con agent/examples.py)
            self._update_history(email_content)
            
            # Rimuovi draft
            os.remove(draft_path)
            self.logger.info(f"Draft rimosso: {draft_path}")
            
            return ApprovalResult(
                status=StepStatus.SUCCESS,
                message="Draft approvato e archiviato",
                archive_path=archive_path,
                added_to_memory=memory_added
            )
            
        except Exception as e:
            self.logger.error(f"Errore approvazione: {e}", exc_info=True)
            return ApprovalResult(
                status=StepStatus.FAILED,
                message="Errore durante approvazione",
                error=str(e)
            )
    
    def _get_draft_path(self) -> str:
        """Ottiene path completo del draft."""
        return os.path.join(
            self.config['execution']['output_dir'],
            self.config['execution']['draft_filename']
        )
    
    def _extract_email_content(self, full_content: str) -> str:
        """Estrae contenuto email rimuovendo header metadata."""
        if "---" in full_content:
            parts = full_content.split("---", 1)
            if len(parts) == 2:
                return parts[1].strip()
        return full_content
    
    def _interactive_approval(self, content: str) -> bool:
        """Mostra draft e chiede conferma."""
        print("\n" + "=" * 70)
        print("  📧 DRAFT EMAIL - REVIEW")
        print("=" * 70)
        print()
        print(content)
        print()
        print("=" * 70)
        print()
        
        while True:
            print("Vuoi approvare questo draft?")
            print("  [s/y] Sì, approva")
            print("  [n]   No, rifiuta")
            print()
            response = input("Scelta: ").strip().lower()
            
            if response in ('s', 'si', 'sì', 'y', 'yes'):
                return True
            if response in ('n', 'no'):
                return False
            print("Risposta non valida.\n")
    
    def _archive_draft(self, draft_path: str) -> str:
        """Archivia draft approvato con timestamp."""
        archive_dir = self.config['execution']['archive_dir']
        os.makedirs(archive_dir, exist_ok=True)
        
        timestamp_format = self.config.get('advanced', {}).get(
            'timestamp_format', '%Y%m%d_%H%M%S'
        )
        timestamp = datetime.now().strftime(timestamp_format)
        archive_filename = f"email_{timestamp}.md"
        archive_path = os.path.join(archive_dir, archive_filename)
        
        # Copia con header approvazione
        with open(draft_path, 'r', encoding='utf-8') as src:
            content = src.read()
        
        approval_header = f"""<!-- APPROVATO IL: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->
<!-- AGGIUNTO ALLA MEMORIA REDIS -->

"""
        with open(archive_path, 'w', encoding='utf-8') as dst:
            dst.write(approval_header + content)
        
        self.logger.info(f"Draft archiviato: {archive_path}")
        return archive_path
    
    def _add_to_redis_memory(self, email_content: str) -> bool:
        """Aggiunge email approvata a Redis Memory per few-shot learning."""
        try:
            from agent.load_memory import add_approved_message
            success = add_approved_message(email_content, config_path="config.yaml")
            
            if success:
                self.logger.info("Email aggiunta a Redis Memory")
            else:
                self.logger.warning("Impossibile aggiungere a Redis Memory")
            
            return success
            
        except ImportError:
            self.logger.warning("Modulo agent.load_memory non disponibile")
            return False
        except Exception as e:
            self.logger.warning(f"Errore aggiunta a Redis Memory: {e}")
            return False
    
    def _update_history(self, email_content: str) -> None:
        """
        Aggiunge email a history.md in formato compatibile con agent/examples.py.
        
        Formato richiesto: ## EMAIL dd/mm/yyyy DD-MM-YYYY
        """
        try:
            from agent.examples import add_new_example
            
            date_str = datetime.now().strftime('%d-%m-%Y')
            add_new_example(email_content, date_str, file_path="history.md")
            self.logger.info("History.md aggiornato")
            
        except ImportError:
            self.logger.warning("Modulo agent.examples non disponibile, skip update history")
        except Exception as e:
            self.logger.warning(f"Errore aggiornamento history: {e}")

