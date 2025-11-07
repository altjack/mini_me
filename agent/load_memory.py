"""Gestione memoria Redis per l'agente AI."""

import redis
import json
import os
import yaml
from typing import Dict, List, Any, Optional
from datetime import datetime


def get_redis_connection(config_path: str = "config.yaml") -> redis.Redis:
    """
    Crea connessione Redis da configurazione.
    
    Args:
        config_path: Percorso al file di configurazione
    
    Returns:
        Istanza Redis connessa
    """
    # Carica configurazione se esiste, altrimenti usa default
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            redis_config = config.get('redis', {})
    else:
        redis_config = {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'memory_prefix': 'agent:memory:weborder'
        }
    
    return redis.Redis(
        host=redis_config.get('host', 'localhost'),
        port=redis_config.get('port', 6379),
        db=redis_config.get('db', 0),
        decode_responses=True
    )


def load_initial_memory(conversation_file: str = "conversation_weborder.json", 
                       config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Carica la memoria iniziale da file JSON a Redis.
    
    Questa funzione va eseguita UNA TANTUM per popolare Redis con lo storico
    della conversazione "Weborder Residential Performance Update".
    
    Args:
        conversation_file: Percorso al file JSON con la conversazione
        config_path: Percorso al file di configurazione
    
    Returns:
        Dizionario con statistiche del caricamento
    """
    # Verifica che il file esista
    if not os.path.exists(conversation_file):
        raise FileNotFoundError(f"File conversazione non trovato: {conversation_file}")
    
    # Carica conversazione
    with open(conversation_file, 'r', encoding='utf-8') as f:
        conversation = json.load(f)
    
    # Connessione Redis
    r = get_redis_connection(config_path)
    
    # Carica configurazione per prefix
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            prefix = config.get('redis', {}).get('memory_prefix', 'agent:memory:weborder')
    else:
        prefix = 'agent:memory:weborder'
    
    # Pulisci memoria esistente (se presente)
    keys_to_delete = r.keys(f"{prefix}:*")
    if keys_to_delete:
        r.delete(*keys_to_delete)
        print(f"✓ Pulite {len(keys_to_delete)} chiavi esistenti")
    
    # Salva metadata conversazione
    metadata = {
        'uuid': conversation.get('uuid'),
        'name': conversation.get('name'),
        'created_at': conversation.get('created_at'),
        'updated_at': conversation.get('updated_at'),
        'loaded_at': datetime.now().isoformat()
    }
    r.set(f"{prefix}:metadata", json.dumps(metadata))
    
    # Salva messaggi
    messages = conversation.get('chat_messages', [])
    message_count = 0
    
    for msg in messages:
        # Estrai solo i campi rilevanti
        clean_message = {
            'sender': msg.get('sender'),
            'text': msg.get('text'),
            'created_at': msg.get('created_at'),
        }
        r.rpush(f"{prefix}:messages", json.dumps(clean_message))
        message_count += 1
    
    # Salva contatore
    r.set(f"{prefix}:count", message_count)
    
    stats = {
        'conversation_name': conversation.get('name'),
        'messages_loaded': message_count,
        'prefix': prefix,
        'timestamp': datetime.now().isoformat()
    }
    
    print(f"\n✓ Memoria caricata con successo!")
    print(f"  - Conversazione: {stats['conversation_name']}")
    print(f"  - Messaggi caricati: {stats['messages_loaded']}")
    print(f"  - Prefix Redis: {stats['prefix']}")
    
    return stats


def get_memory_context(config_path: str = "config.yaml", 
                      max_messages: Optional[int] = None) -> str:
    """
    Recupera il contesto della memoria da Redis per l'agente.
    
    Args:
        config_path: Percorso al file di configurazione
        max_messages: Limite opzionale sul numero di messaggi (None = tutti)
    
    Returns:
        Stringa formattata con il contesto della memoria
    """
    r = get_redis_connection(config_path)
    
    # Carica configurazione per prefix
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            prefix = config.get('redis', {}).get('memory_prefix', 'agent:memory:weborder')
    else:
        prefix = 'agent:memory:weborder'
    
    # Verifica che la memoria esista
    if not r.exists(f"{prefix}:messages"):
        return "MEMORIA STORICA: Nessuna memoria caricata. Esegui load_initial_memory() prima."
    
    # Carica metadata
    metadata_str = r.get(f"{prefix}:metadata")
    metadata = json.loads(metadata_str) if metadata_str else {}
    
    # Carica messaggi
    message_count = int(r.get(f"{prefix}:count") or 0)
    
    # Applica limite se specificato
    if max_messages and max_messages < message_count:
        # Prendi gli ultimi N messaggi
        messages_raw = r.lrange(f"{prefix}:messages", -max_messages, -1)
    else:
        messages_raw = r.lrange(f"{prefix}:messages", 0, -1)
    
    messages = [json.loads(msg) for msg in messages_raw]
    
    # Formatta contesto per il prompt
    context = f"""
=== MEMORIA STORICA: {metadata.get('name', 'Conversazione')} ===

Hai accesso allo storico completo di {len(messages)} messaggi dalla conversazione 
"{metadata.get('name', 'Unknown')}" (creata il {metadata.get('created_at', 'N/A')}).

Questa conversazione contiene esempi del tuo lavoro precedente sulla generazione di 
email giornaliere per report GA4, con focus su weborder_residenziale.

STILE E FORMATO APPRESO:
"""
    
    # Aggiungi alcuni esempi rappresentativi
    for i, msg in enumerate(messages[:6]):  # Prime 3 iterazioni (6 messaggi)
        sender_label = "UTENTE" if msg['sender'] == 'human' else "ASSISTENTE"
        text_preview = msg['text'][:300] + "..." if len(msg['text']) > 300 else msg['text']
        context += f"\n[{sender_label} - {msg.get('created_at', 'N/A')[:10]}]:\n{text_preview}\n"
    
    if len(messages) > 6:
        context += f"\n... ({len(messages) - 6} messaggi aggiuntivi in memoria) ...\n"
    
    context += """
ISTRUZIONI:
- Mantieni lo STESSO STILE professionale ma discorsivo dimostrato negli esempi
- Usa la STESSA STRUTTURA vista nelle email precedenti
- Enfatizza le metriche chiave: SWI, CR commodity, CR canalizzazione, sessioni
- Focus principale: performance weborder_residenziale come KPI cliente
- Includi confronti percentuali rispetto ai periodi precedenti
- Tono: conciso ma informativo

=== FINE MEMORIA STORICA ===
"""
    
    return context


def add_approved_message(message_text: str, config_path: str = "config.yaml") -> bool:
    """
    Aggiunge un messaggio approvato alla memoria Redis.
    
    Args:
        message_text: Testo del messaggio da aggiungere
        config_path: Percorso al file di configurazione
    
    Returns:
        True se aggiunto con successo, False altrimenti
    """
    try:
        r = get_redis_connection(config_path)
        
        # Carica configurazione per prefix
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                prefix = config.get('redis', {}).get('memory_prefix', 'agent:memory:weborder')
        else:
            prefix = 'agent:memory:weborder'
        
        # Crea nuovo messaggio
        new_message = {
            'sender': 'assistant',
            'text': message_text,
            'created_at': datetime.now().isoformat(),
            'approved': True
        }
        
        # Aggiungi a Redis
        r.rpush(f"{prefix}:messages", json.dumps(new_message))
        r.incr(f"{prefix}:count")
        
        return True
    except Exception as e:
        print(f"Errore nell'aggiungere messaggio: {e}")
        return False


def get_memory_stats(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Ottiene statistiche sulla memoria caricata.
    
    Args:
        config_path: Percorso al file di configurazione
    
    Returns:
        Dizionario con statistiche
    """
    r = get_redis_connection(config_path)
    
    # Carica configurazione per prefix
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            prefix = config.get('redis', {}).get('memory_prefix', 'agent:memory:weborder')
    else:
        prefix = 'agent:memory:weborder'
    
    metadata_str = r.get(f"{prefix}:metadata")
    metadata = json.loads(metadata_str) if metadata_str else {}
    
    message_count = int(r.get(f"{prefix}:count") or 0)
    
    return {
        'conversation_name': metadata.get('name', 'N/A'),
        'total_messages': message_count,
        'loaded_at': metadata.get('loaded_at', 'N/A'),
        'redis_prefix': prefix
    }


if __name__ == "__main__":
    """
    Script eseguibile per setup iniziale memoria.
    """
    import sys
    
    print("=== Setup Memoria Redis ===\n")
    
    # Verifica che Redis sia attivo
    try:
        r = get_redis_connection()
        r.ping()
        print("✓ Redis connesso e funzionante\n")
    except redis.ConnectionError:
        print("❌ ERRORE: Redis non è in esecuzione!")
        print("\nPer avviare Redis:")
        print("  macOS: brew install redis && redis-server")
        print("  Linux: sudo apt-get install redis-server && redis-server")
        sys.exit(1)
    
    # Carica memoria iniziale
    try:
        stats = load_initial_memory()
        
        # Mostra statistiche
        print("\n=== Statistiche Memoria ===")
        final_stats = get_memory_stats()
        for key, value in final_stats.items():
            print(f"  {key}: {value}")
        
        print("\n✓ Setup completato! Ora puoi eseguire: python run_agent.py")
        
    except FileNotFoundError as e:
        print(f"\n❌ ERRORE: {e}")
        print("\nAssicurati che il file 'conversation_weborder.json' sia nella directory corrente.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERRORE imprevisto: {e}")
        sys.exit(1)

