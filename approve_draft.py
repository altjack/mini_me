#!/usr/bin/env python3
"""
Script per approvare draft email e aggiungere alla memoria Redis.

Usage:
    uv run approve_draft.py
    
Questo script:
1. Legge il draft email da email/draft_email.md
2. Mostra il contenuto per review
3. Chiede conferma approvazione
4. Se approvato: aggiunge alla memoria Redis e archivia
5. Se rifiutato: mantiene il draft per modifiche

Workflow:
    run_agent.py -> draft_email.md -> [QUESTO SCRIPT] -> Redis memory + archive
"""

import yaml
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Aggiungi directory corrente al path
sys.path.append(os.path.dirname(__file__))

from agent.load_memory import add_approved_message, get_memory_stats


def load_config(config_path: str = "config.yaml") -> dict:
    """
    Carica configurazione da file YAML.
    
    Args:
        config_path: Percorso al file di configurazione
    
    Returns:
        Dizionario con configurazione
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"File di configurazione non trovato: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config


def read_draft(config: dict) -> tuple[str, str]:
    """
    Legge il contenuto del draft email.
    
    Args:
        config: Dizionario configurazione
    
    Returns:
        Tuple (percorso_file, contenuto)
    """
    output_dir = config['execution']['output_dir']
    draft_filename = config['execution']['draft_filename']
    draft_path = os.path.join(output_dir, draft_filename)
    
    if not os.path.exists(draft_path):
        raise FileNotFoundError(
            f"Draft non trovato: {draft_path}\n"
            "Esegui prima: uv run run_agent.py"
        )
    
    with open(draft_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return draft_path, content


def extract_email_content(full_content: str) -> str:
    """
    Estrae il contenuto email dal draft (rimuove header metadata).
    
    Args:
        full_content: Contenuto completo del draft con header
    
    Returns:
        Contenuto email pulito
    """
    # Cerca il separatore "---" che divide header da contenuto
    if "---" in full_content:
        parts = full_content.split("---", 1)
        if len(parts) == 2:
            return parts[1].strip()
    
    # Se non trova separatore, ritorna tutto
    return full_content


def display_draft(content: str) -> None:
    """
    Mostra il draft formattato per review.
    
    Args:
        content: Contenuto draft da mostrare
    """
    print()
    print("=" * 70)
    print("  📧 DRAFT EMAIL - REVIEW")
    print("=" * 70)
    print()
    print(content)
    print()
    print("=" * 70)
    print()


def get_user_approval() -> bool:
    """
    Chiede approvazione all'utente.
    
    Returns:
        True se approvato, False altrimenti
    """
    while True:
        print("Vuoi approvare questo draft e aggiungerlo alla memoria?")
        print()
        print("  [y] Sì, approva e aggiungi alla memoria")
        print("  [n] No, rifiuta (mantieni draft per modifiche)")
        print("  [v] Visualizza di nuovo il draft")
        print()
        
        choice = input("Scelta: ").strip().lower()
        
        if choice == 'y':
            return True
        elif choice == 'n':
            return False
        elif choice == 'v':
            return None  # Segnale per ri-mostrare
        else:
            print("❌ Scelta non valida. Usa 'y', 'n' o 'v'.\n")


def archive_draft(draft_path: str, config: dict) -> str:
    """
    Archivia il draft approvato con timestamp.
    
    Args:
        draft_path: Percorso al file draft
        config: Dizionario configurazione
    
    Returns:
        Percorso al file archiviato
    """
    archive_dir = config['execution']['archive_dir']
    timestamp_format = config.get('advanced', {}).get('timestamp_format', '%Y%m%d_%H%M%S')
    timestamp = datetime.now().strftime(timestamp_format)
    
    # Crea nome file archivio
    archive_filename = f"email_{timestamp}.md"
    archive_path = os.path.join(archive_dir, archive_filename)
    
    # Copia il file
    with open(draft_path, 'r', encoding='utf-8') as src:
        content = src.read()
    
    # Aggiungi header approvazione
    approval_header = f"""<!-- APPROVATO IL: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->
<!-- AGGIUNTO ALLA MEMORIA REDIS -->

"""
    
    with open(archive_path, 'w', encoding='utf-8') as dst:
        dst.write(approval_header)
        dst.write(content)
    
    return archive_path


def delete_draft(draft_path: str) -> None:
    """
    Elimina il file draft dopo approvazione.
    
    Args:
        draft_path: Percorso al file draft da eliminare
    """
    if os.path.exists(draft_path):
        os.remove(draft_path)


def show_memory_stats() -> None:
    """
    Mostra statistiche memoria aggiornate.
    """
    try:
        stats = get_memory_stats()
        print("\n📊 STATISTICHE MEMORIA AGGIORNATE:")
        print(f"   • Conversazione: {stats['conversation_name']}")
        print(f"   • Totale messaggi: {stats['total_messages']}")
        print(f"   • Caricata il: {stats['loaded_at']}")
    except Exception as e:
        print(f"\n⚠️  Impossibile ottenere statistiche: {e}")


def approve_draft_workflow(config: dict, interactive: bool = True) -> tuple[bool, str]:
    """
    Esegue il workflow di approvazione draft email.
    
    Args:
        config: Dizionario configurazione
        interactive: Se True, chiede approvazione utente. Se False, approva automaticamente.
    
    Returns:
        Tuple (approvato: bool, archive_path: str o None)
        
    Raises:
        FileNotFoundError: Se draft non trovato
        Exception: Se approvazione fallisce
    """
    # 1. Leggi draft
    draft_path, full_content = read_draft(config)
    email_content = extract_email_content(full_content)
    
    # 2. Se non interattivo, approva automaticamente
    if not interactive:
        approval = True
    else:
        # Loop di review interattivo
        while True:
            display_draft(email_content)
            
            approval = get_user_approval()
            
            if approval is None:
                # Utente ha scelto 'v' per visualizzare di nuovo
                continue
            else:
                break
    
    # 3. Se rifiutato, ritorna False
    if not approval:
        return False, None
    
    # 4. APPROVATO - Aggiungi a memoria Redis
    try:
        success = add_approved_message(email_content, config_path="config.yaml")
        
        if not success:
            raise RuntimeError("Errore nell'aggiunta alla memoria Redis")
            
    except Exception as e:
        raise RuntimeError(
            f"Errore Redis: {e}\n"
            "Verifica che Redis sia attivo: redis-server"
        )
    
    # 5. Archivia draft
    archive_path = archive_draft(draft_path, config)
    
    # 6. Elimina draft corrente
    delete_draft(draft_path)
    
    # 7. Aggiungi a history.md
    try:
        from agent.examples import add_new_example
        date_str = datetime.now().strftime('%d-%m-%Y')
        add_new_example(email_content, date_str, file_path="history.md")
    except Exception as e:
        # Non critico, continua
        print(f"⚠️ Warning: Impossibile aggiornare history.md: {e}")
    
    return True, archive_path


def main():
    """
    Funzione principale per approvazione standalone (retrocompatibilità).
    """
    print("=" * 70)
    print("  📋 APPROVAL WORKFLOW - Review e Approvazione Draft")
    print("=" * 70)
    
    try:
        # 1. Carica configurazione
        print("\n📋 Caricamento configurazione...")
        config = load_config()
        print("✓ Configurazione caricata")
        
        # 2. Leggi draft
        print("📧 Lettura draft email...")
        draft_path, full_content = read_draft(config)
        email_content = extract_email_content(full_content)
        print(f"✓ Draft caricato da: {draft_path}")
        
        # 3. Esegui workflow interattivo
        approved, archive_path = approve_draft_workflow(config, interactive=True)
        
        if approved:
            # APPROVATO
            print("\n✓ Draft approvato!\n")
            print("💾 Aggiunta alla memoria Redis...")
            print("✓ Messaggio aggiunto alla memoria Redis")
            print("📁 Archiviazione draft...")
            print(f"✓ Draft archiviato: {archive_path}")
            print(f"✓ Draft rimosso: {draft_path}")
            
            # Mostra statistiche
            show_memory_stats()
            
            # Successo finale
            print("\n" + "=" * 70)
            print("  ✅ APPROVAZIONE COMPLETATA CON SUCCESSO")
            print("=" * 70)
            print()
            print("📝 Il draft è stato:")
            print(f"   ✓ Aggiunto alla memoria Redis per futuri riferimenti")
            print(f"   ✓ Archiviato in: {archive_path}")
            print(f"   ✓ Rimosso dalla cartella draft")
            print()
            print("🚀 Prossima esecuzione:")
            print("   uv run run_agent.py")
            print()
        else:
            # RIFIUTATO
            print("\n❌ Draft rifiutato")
            print()
            print("Il draft è stato mantenuto per modifiche.")
            print()
            print("📝 OPZIONI:")
            print("   1. Modifica config.yaml e riesegui: uv run run_agent.py")
            print("   2. Modifica manualmente il draft e riapprova: uv run approve_draft.py")
            print(f"   3. Percorso draft: {draft_path}")
            print()
        
    except FileNotFoundError as e:
        print(f"\n❌ ERRORE: {e}")
        sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Operazione annullata dall'utente")
        sys.exit(130)
    
    except Exception as e:
        print(f"\n❌ ERRORE IMPREVISTO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

