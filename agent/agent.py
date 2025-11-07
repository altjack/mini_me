"""Agent configuration with Redis memory integration."""

from datapizza.agents import Agent
from datapizza.clients.anthropic import AnthropicClient
from dotenv import load_dotenv
import os
import sys


# Aggiungi il percorso corrente al path per gli import
sys.path.append(os.path.dirname(__file__))

load_dotenv()

# Import dei componenti necessari
from prompt import SYSTEM_PROMPT
from tools import (
    get_daily_report,
    get_metrics_summary,
    get_product_performance,
    compare_periods
)
from examples import load_examples, sample_examples, format_examples_for_prompt
# from load_memory import get_memory_context  # DEPRECATED: usa examples invece

client_anthropic = AnthropicClient(api_key=os.getenv('ANTHROPIC_API_KEY'), model="claude-sonnet-4-5-20250929")

def create_agent_with_memory(model: str = "claude-sonnet-4-5-20250929", verbose: bool = True) -> Agent:
    """
    Crea un'istanza dell'agente con esempi email da history.md.
    
    L'agente ha accesso a:
    - Esempi di email precedenti da history.md per few-shot learning
    - Tools per estrarre e analizzare dati GA4 dal database
    
    Args:
        model: Nome del modello Anthropic da utilizzare
        verbose: Se True, mostra output dettagliato durante l'esecuzione
    
    Returns:
        Istanza Agent configurata e pronta all'uso
    """
    # Verifica API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY non trovata nelle variabili d'ambiente.\n"
            "Aggiungi la chiave nel file .env"
        )
    
    # Crea client Anthropic con modello specificato
    
    # Carica esempi email da history.md
    try:
        all_examples = load_examples("history.md")
        selected_examples = sample_examples(all_examples, n=6, strategy="recent_weighted")
        examples_context = format_examples_for_prompt(selected_examples)
    except Exception as e:
        print(f"⚠️ Warning: Impossibile caricare esempi: {e}")
        print("L'agente funzionerà senza esempi di riferimento.")
        examples_context = ""
    
    # System prompt arricchito con esempi
    enhanced_prompt = f"{SYSTEM_PROMPT}\n\n{examples_context}"
    
    # Lista tools disponibili
    available_tools = [
        get_daily_report,
        get_metrics_summary,
        get_product_performance,
        compare_periods
    ]
    
    # Crea agent
    agent = Agent(
        name="DailyReportAgent",
        client=client_anthropic,
        system_prompt=enhanced_prompt,
        tools=available_tools
    )
    
    return agent


def create_agent_without_memory(model: str = "claude-sonnet-4-5-20250929", verbose: bool = True) -> Agent:
    """
    Crea un'istanza dell'agente SENZA memoria Redis.
    
    Utile per testing o quando Redis non è disponibile.
    
    Args:
        model: Nome del modello Anthropic da utilizzare
        verbose: Se True, mostra output dettagliato
    
    Returns:
        Istanza Agent configurata senza memoria storica
    """
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY non trovata nelle variabili d'ambiente.")
    

    
    available_tools = [
        get_daily_report,
        get_metrics_summary,
        get_product_performance,
        compare_periods
    ]
    
    agent = Agent(
        name="DailyReportAgentNoMemory",
        client=client_anthropic,
        system_prompt=SYSTEM_PROMPT,
        tools=available_tools
    )
    
    return agent


if __name__ == "__main__":
    """
    Test dell'agente. Per esecuzione normale, usa run_agent.py
    """
    print("=== Test Agent ===\n")
    
    try:
        # Prova con memoria
        print("Creazione agente con memoria Redis...")
        agent = create_agent_with_memory(verbose=True)
        print("✓ Agente creato con successo!")
        
        # Test semplice
        print("\n--- Test Query ---")
        response = agent.run("Quali tool hai a disposizione?")
        print(f"\nRisposta: {response}")
        
    except Exception as e:
        print(f"❌ Errore durante il test: {e}")
        print("\nProva ad eseguire:")
        print("  1. redis-server  # Avvia Redis")
        print("  2. python agent/load_memory.py  # Carica memoria")
        print("  3. python agent/agent.py  # Riprova il test")
