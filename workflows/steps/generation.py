"""
Generation step implementation.

Handles email generation with AI Agent:
- Creates agent with memory
- Executes task prompt
- Saves draft to file
- Uses ToolSession for efficient connection management
"""

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from workflows.result_types import GenerationResult, StepStatus
from agent.session import ToolSession


class GenerationStep:
    """
    Implementazione step generazione email.
    
    Incapsula la logica di run_agent senza dipendenze circolari.
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
        skip_data_check: bool = False
    ) -> GenerationResult:
        """
        Esegue generazione email con AI Agent.
        
        Args:
            skip_data_check: Salta verifica disponibilità dati
            
        Returns:
            GenerationResult con esito operazione
        """
        try:
            self.logger.info("Inizio generazione email con AI Agent...")
            
            # Import locale per evitare dipendenza circolare a livello di modulo
            # Questo è accettabile perché:
            # 1. L'import avviene solo quando il metodo è chiamato
            # 2. Non c'è dipendenza circolare a livello di modulo
            # 3. Il costo dell'import è ammortizzato (Python cache)
            from agent.agent import create_agent_with_memory
            
            # Crea agent
            model = self.config['agent']['model']
            verbose = self.config['agent'].get('verbose', True)
            agent = create_agent_with_memory(model=model, verbose=verbose)
            
            # Esegui task con ToolSession per connessioni condivise
            # Questo evita che ogni tool apra/chiuda connessioni DB/Redis
            task_prompt = self.config['execution']['task_prompt']
            self.logger.info(f"Task prompt: {task_prompt[:100]}...")
            
            with ToolSession(self.config) as session:
                self.logger.debug("ToolSession avviata per esecuzione agent")
                result = agent.run(task_prompt)
            
            # Estrai contenuto
            content = self._extract_content(result)
            
            if not content or len(content) < 100:
                return GenerationResult(
                    status=StepStatus.FAILED,
                    message="Contenuto generato troppo corto",
                    error="L'agent non ha prodotto un'email valida"
                )
            
            # Salva draft
            draft_path = self._save_draft(content)
            
            return GenerationResult(
                status=StepStatus.SUCCESS,
                message="Draft generato con successo",
                draft_path=draft_path
            )
            
        except Exception as e:
            self.logger.error(f"Errore generazione: {e}", exc_info=True)
            return GenerationResult(
                status=StepStatus.FAILED,
                message="Errore durante generazione",
                error=str(e)
            )
    
    def _extract_content(self, result) -> str:
        """
        Estrae contenuto testuale dal risultato agent.
        
        Gestisce vari tipi di risultato (StepResult, liste, stringhe).
        """
        def extract_recursive(obj):
            """Estrae ricorsivamente il contenuto da qualsiasi tipo di oggetto"""
            if isinstance(obj, str):
                return obj
            elif isinstance(obj, list):
                # Per liste, cerca elementi con content/text e skip tool calls
                parts = []
                for item in obj:
                    # Skip FunctionCallBlock e FunctionCallResultBlock
                    item_type = type(item).__name__
                    if 'FunctionCall' in item_type or 'Block' in item_type:
                        continue
                    
                    extracted = extract_recursive(item)
                    if extracted and extracted.strip():
                        parts.append(extracted)
                return "\n".join(parts) if parts else ""
            # Per StepResult, accedi direttamente all'attributo text
            elif hasattr(obj, 'text'):
                text_val = obj.text
                # Se text è una stringa, ritornala
                if isinstance(text_val, str):
                    return text_val
                # Altrimenti recursione
                return extract_recursive(text_val)
            # Prova altri attributi comuni
            elif hasattr(obj, 'content'):
                content = obj.content
                # Se content è una lista, filtra tool blocks
                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if hasattr(item, 'text'):
                            text_parts.append(item.text)
                        elif isinstance(item, str):
                            text_parts.append(item)
                    return "\n".join(text_parts) if text_parts else extract_recursive(content)
                return extract_recursive(content)
            elif hasattr(obj, 'message'):
                return extract_recursive(obj.message)
            else:
                # Solo come ultimo resort
                obj_str = str(obj)
                # Se contiene "FunctionCall" o "Block", ritorna vuoto
                if 'FunctionCall' in obj_str or 'Block' in obj_str:
                    return ""
                return obj_str
        
        result_str = extract_recursive(result)
        
        # Filtra righe JSON dei tool calls
        if result_str:
            lines = result_str.split('\n')
            filtered_lines = []
            for line in lines:
                stripped = line.strip()
                # Skip righe che sembrano JSON di tool calls
                if stripped.startswith('{"type":') and ('"tool_call"' in stripped or '"tool_result"' in stripped):
                    continue
                filtered_lines.append(line)
            result_str = '\n'.join(filtered_lines)
        
        return result_str
    
    def _save_draft(self, content: str) -> str:
        """Salva draft email su file"""
        output_dir = self.config['execution']['output_dir']
        draft_filename = self.config['execution']['draft_filename']
        draft_path = os.path.join(output_dir, draft_filename)
        
        # Header metadata
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        header = f"""# Draft Email - {timestamp}

**Status:** In attesa di approvazione  
**Generated by:** Agent Daily Report  
**Data source:** {self.config['execution'].get('data_source', 'GA4 Database')}

---

"""
        
        os.makedirs(output_dir, exist_ok=True)
        with open(draft_path, 'w', encoding='utf-8') as f:
            f.write(header + content)
        
        self.logger.info(f"Draft salvato: {draft_path}")
        return draft_path

