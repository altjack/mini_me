"""Agent configuration with Redis memory integration."""

from datapizza.agents import Agent
from datapizza.clients.anthropic import AnthropicClient
from datapizza.clients.openai import OpenAIClient
from dotenv import load_dotenv
import os
import sys


load_dotenv()

# Import dei componenti necessari
from backend.agent.prompt import SYSTEM_PROMPT
from backend.agent.tools import (
    get_daily_report,
    get_weekend_report,
    compare_periods,
    get_active_promos,
    compare_promo_periods
)
from backend.agent.examples import load_examples, sample_examples, format_examples_for_prompt
# from load_memory import get_memory_context  # DEPRECATED: usa examples invece

def client_anthropic(model):
    return AnthropicClient(api_key=os.getenv('ANTHROPIC_API_KEY'),model=model)
def client_openai(model):
    return OpenAIClient(api_key=os.getenv('OPENAI_API_KEY'), model=model)

def create_agent_with_memory(model: str = "claude-haiku-4-5-20251001", verbose: bool = True) -> Agent:
    """
    Crea un'istanza dell'agente con esempi email da history.md.
    
    L'agente ha accesso a:
    - Esempi di email precedenti da history.md per few-shot learning
    - Tools per estrarre e analizzare dati GA4 dal database
    
    Args:
        model: Nome del modello da utilizzare (default: "claude-haiku-4-5-20251001")
        verbose: Se True, mostra log dettagliati (default: True)
    
    Returns:
        Istanza Agent configurata e pronta all'uso
    """    
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
        get_weekend_report,  # Alias legacy per retrocompatibilità
        compare_periods,  # Per analisi custom multi-periodo
        get_active_promos,  # Per verificare promozioni attive
        compare_promo_periods  # Per confrontare periodi con promo diverse
    ]
    
    # Crea agent
    agent = Agent(
        name="DailyReportAgent",
        client=client_anthropic(model=model),
        system_prompt=enhanced_prompt,
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
