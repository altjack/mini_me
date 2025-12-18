"""
Gestione esempi email per few-shot learning.

Questo modulo sostituisce il sistema di memoria Redis con un approccio
semplificato basato su file markdown contenente esempi di email complete.
"""

import re
import random
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
import os


@dataclass
class EmailExample:
    """Rappresenta un esempio di email dal file history."""
    date: datetime
    content: str
    token_count: int
    
    def __repr__(self) -> str:
        return f"EmailExample(date={self.date.strftime('%d-%m-%Y')}, tokens={self.token_count})"


def estimate_tokens(text: str) -> int:
    """
    Stima approssimativa del numero di token.
    
    Usa regola empirica: 1 token ≈ 4 caratteri per italiano.
    
    Args:
        text: Testo da analizzare
    
    Returns:
        Numero stimato di token
    """
    return len(text) // 4


def load_examples(file_path: str = "history.md") -> List[EmailExample]:
    """
    Carica esempi email dal file markdown.
    
    Parser per formato:
    ## EMAIl dd/mm/yyyy DD-MM-YYYY
    [contenuto email]
    
    Args:
        file_path: Percorso al file markdown con esempi
    
    Returns:
        Lista di EmailExample ordinata per data (più recente prima)
    
    Raises:
        FileNotFoundError: Se il file non esiste
        ValueError: Se il file è vuoto o malformato
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File esempi non trovato: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if not content.strip():
        raise ValueError(f"File esempi vuoto: {file_path}")
    
    # Pattern per header email: ## EMAIl dd/mm/yyyy DD-MM-YYYY
    pattern = r"## EMAIl dd/mm/yyyy (\d{2}-\d{2}-\d{4})"
    
    # Trova tutte le corrispondenze
    matches = list(re.finditer(pattern, content))
    
    if not matches:
        raise ValueError(f"Nessuna email trovata nel file {file_path}. "
                        "Formato atteso: ## EMAIl dd/mm/yyyy DD-MM-YYYY")
    
    examples = []
    
    for i, match in enumerate(matches):
        # Estrai data
        date_str = match.group(1)
        try:
            email_date = datetime.strptime(date_str, '%d-%m-%Y')
        except ValueError:
            print(f"⚠️ Warning: Data malformata '{date_str}', skip email")
            continue
        
        # Estrai contenuto email (da dopo header fino al prossimo header o fine file)
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        
        email_content = content[start_pos:end_pos].strip()
        
        # Validazione: skip email vuote
        if not email_content or len(email_content) < 50:
            print(f"⚠️ Warning: Email del {date_str} troppo corta o vuota, skip")
            continue
        
        # Crea EmailExample
        example = EmailExample(
            date=email_date,
            content=email_content,
            token_count=estimate_tokens(email_content)
        )
        
        examples.append(example)
    
    if not examples:
        raise ValueError(f"Nessuna email valida estratta da {file_path}")
    
    # Ordina per data (più recente prima)
    examples.sort(key=lambda x: x.date, reverse=True)
    
    print(f"✓ Caricate {len(examples)} email da {file_path}")
    print(f"  Range date: {examples[-1].date.strftime('%d/%m/%Y')} → {examples[0].date.strftime('%d/%m/%Y')}")
    
    return examples


def sample_examples(
    examples: List[EmailExample],
    n: int = 6,
    strategy: str = "recent_weighted"
) -> List[EmailExample]:
    """
    Seleziona N esempi dalla lista usando la strategia specificata.
    
    Strategie disponibili:
    - "recent": Prende le ultime N email (più recenti)
    - "recent_weighted": Sampling pesato che favorisce email recenti
    - "random": Sampling casuale uniforme
    
    Args:
        examples: Lista completa di esempi
        n: Numero di esempi da selezionare
        strategy: Strategia di sampling
    
    Returns:
        Lista di N esempi selezionati (ordinati per data, più recente prima)
    
    Raises:
        ValueError: Se strategia non riconosciuta
    """
    if not examples:
        return []
    
    # Se richiesti più esempi di quelli disponibili, ritorna tutti
    if n >= len(examples):
        return examples
    
    if strategy == "recent":
        # Semplice: prende le prime N (già ordinate per data decrescente)
        selected = examples[:n]
        
    elif strategy == "recent_weighted":
        # Sampling pesato: più recente = più probabilità
        # Pesi: 1.0, 0.5, 0.33, 0.25, ... (inversamente proporzionali alla posizione)
        weights = [1.0 / (i + 1) for i in range(len(examples))]
        
        # Campionamento pesato senza replacement
        selected = random.choices(examples, weights=weights, k=n)
        
        # Riordina per data (più recente prima)
        selected.sort(key=lambda x: x.date, reverse=True)
        
    elif strategy == "random":
        # Sampling casuale uniforme
        selected = random.sample(examples, k=n)
        
        # Riordina per data (più recente prima)
        selected.sort(key=lambda x: x.date, reverse=True)
        
    else:
        raise ValueError(f"Strategia sampling non riconosciuta: {strategy}. "
                        f"Usa: 'recent', 'recent_weighted', o 'random'")
    
    total_tokens = sum(ex.token_count for ex in selected)
    print(f"✓ Selezionate {len(selected)} email (strategia: {strategy})")
    print(f"  Token stimati: {total_tokens}")
    
    return selected


def format_examples_for_prompt(examples: List[EmailExample]) -> str:
    """
    Formatta esempi in markdown per inclusion nel system prompt.
    
    Output format:
    === ESEMPI EMAIL PRECEDENTI ===
    
    Usa questi esempi come riferimento per formato, stile e struttura.
    
    ---
    ### Email del DD/MM/YYYY
    [contenuto completo]
    
    ---
    ### Email del DD/MM/YYYY
    [contenuto completo]
    
    === FINE ESEMPI ===
    
    Args:
        examples: Lista di esempi da formattare
    
    Returns:
        Stringa markdown formattata
    """
    if not examples:
        return ""
    
    output = "=== ESEMPI EMAIL PRECEDENTI ===\n\n"
    output += "Questi sono esempi REALI di email generate in passato per lo stesso report giornaliero GA4.\n"
    output += "Rappresentano lo STILE e la STRUTTURA che devi EMULARE nelle tue email.\n\n"
    
    output += "**PATTERN DA REPLICARE negli esempi:**\n"
    output += "1. APERTURA: Inizio diretto con la metrica principale (es. 'Mercoledì 30 ottobre registra 256 SWI...')\n"
    output += "2. CONTESTO: Variazione percentuale immediata con confronto temporale (es. '-11% rispetto a mercoledì 22 ottobre')\n"
    output += "3. DETTAGLIO PRODOTTI: Percentuali specifiche per Fixa, Pernoi, Trend, Sempre\n"
    output += "4. FLUSSO NARRATIVO: Sessioni → Analisi canali (se rilevante) → CR → Insights finali\n"
    output += "5. LINGUAGGIO: Professionale ma discorsivo, con frasi articolate e analisi contestuali\n"
    output += "6. ANALISI: Non solo numeri, ma interpretazione e contesto (es. 'confermando la prosecuzione dell\\'effetto delle campagne media')\n"
    output += "7. CHIUSURA: Firma semplice 'Giacomo' senza formule di commiato elaborate\n\n"
    
    output += "**STILE LINGUISTICO DA EMULARE:**\n"
    output += "- Espressioni come: 'registra', 'si attesta su', 'evidenziando', 'confermando', 'trainato principalmente da'\n"
    output += "- Confronti articolati: 'vs [giorno] [data]', 'rispetto a', 'a fronte di'\n"
    output += "- Analisi causali: 'dovuto a', 'generando un impatto', 'risentendo della combinazione'\n"
    output += "- Valutazioni: 'segnale positivo', 'in controtendenza', 'mantiene la predominanza'\n\n"
    
    output += "**ISTRUZIONI CRITICHE:**\n"
    output += "- NON usare template fissi o strutture rigide a paragrafi numerati\n"
    output += "- EMULA il 'flusso narrativo' naturale degli esempi\n"
    output += "- USA le stesse espressioni e formule che vedi ripetute negli esempi\n"
    output += "- MANTIENI il tono analitico ma accessibile, mai troppo formale o burocratico\n"
    output += "- INTEGRA analisi e numeri in modo fluido, non come liste di bullet point\n\n"
    
    output += "---\n\n"
    output += "ESEMPI CONCRETI DA SEGUIRE:\n\n"
    
    for example in examples:
        date_formatted = example.date.strftime('%d/%m/%Y')
        output += "---\n"
        output += f"### Email del {date_formatted}\n\n"
        output += example.content
        output += "\n\n"
    
    output += "---\n\n"
    output += "=== FINE ESEMPI ===\n\n"
    output += "RICORDA: Il tuo compito è scrivere un'email che potrebbe essere confusa con questi esempi per stile e qualità.\n"
    output += "Non copiare pedissequamente, ma EMULA l'approccio, il tono, e la struttura narrativa.\n"
    
    return output


def add_new_example(
    email_content: str,
    date: str,
    file_path: str = "history.md"
) -> None:
    """
    Aggiunge una nuova email in testa al file history.md.
    
    La nuova email viene inserita all'inizio del file per mantenere
    l'ordine cronologico inverso (più recenti in alto).
    
    Args:
        email_content: Contenuto completo della email
        date: Data in formato DD-MM-YYYY
        file_path: Percorso al file markdown
    
    Raises:
        ValueError: Se data non è nel formato corretto
        IOError: Se errore nella scrittura file
    """
    # Valida formato data
    try:
        datetime.strptime(date, '%d-%m-%Y')
    except ValueError:
        raise ValueError(f"Data deve essere in formato DD-MM-YYYY, ricevuto: {date}")
    
    # Prepara nuova entry
    new_entry = f"## EMAIl dd/mm/yyyy {date}\n"
    new_entry += email_content.strip()
    new_entry += "\n\n"
    
    # Leggi contenuto esistente (se esiste)
    existing_content = ""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()
    
    # Scrivi nuova entry + contenuto esistente
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_entry)
        if existing_content:
            # Assicurati che ci sia separazione
            if not existing_content.startswith('\n'):
                f.write('\n')
            f.write(existing_content)
    
    print(f"✓ Email del {date} aggiunta a {file_path}")


def get_examples_stats(examples: List[EmailExample]) -> dict:
    """
    Calcola statistiche sugli esempi caricati.
    
    Args:
        examples: Lista di esempi
    
    Returns:
        Dizionario con statistiche
    """
    if not examples:
        return {
            'total': 0,
            'total_tokens': 0,
            'avg_tokens': 0,
            'date_range': None
        }
    
    total_tokens = sum(ex.token_count for ex in examples)
    
    return {
        'total': len(examples),
        'total_tokens': total_tokens,
        'avg_tokens': total_tokens // len(examples),
        'date_range': f"{examples[-1].date.strftime('%d/%m/%Y')} → {examples[0].date.strftime('%d/%m/%Y')}",
        'oldest': examples[-1].date.strftime('%d/%m/%Y'),
        'newest': examples[0].date.strftime('%d/%m/%Y')
    }


if __name__ == "__main__":
    """
    Test del modulo examples.
    
    Esegui: python agent/examples.py
    """
    print("=== Test Modulo Examples ===\n")
    
    try:
        # Test 1: Caricamento
        print("1. Test caricamento esempi...")
        examples = load_examples("history.md")
        print(f"   ✓ Caricati {len(examples)} esempi\n")
        
        # Test 2: Statistiche
        print("2. Statistiche esempi:")
        stats = get_examples_stats(examples)
        for key, value in stats.items():
            print(f"   {key}: {value}")
        print()
        
        # Test 3: Sampling strategies
        print("3. Test sampling strategies:")
        
        print("   a) Recent (ultime 3):")
        recent = sample_examples(examples, n=3, strategy="recent")
        for ex in recent:
            print(f"      - {ex.date.strftime('%d/%m/%Y')}")
        print()
        
        print("   b) Recent weighted (3 con peso):")
        weighted = sample_examples(examples, n=3, strategy="recent_weighted")
        for ex in weighted:
            print(f"      - {ex.date.strftime('%d/%m/%Y')}")
        print()
        
        print("   c) Random (3 casuali):")
        rand = sample_examples(examples, n=3, strategy="random")
        for ex in rand:
            print(f"      - {ex.date.strftime('%d/%m/%Y')}")
        print()
        
        # Test 4: Formatting
        print("4. Test formatting (prime 2 email):")
        sample = sample_examples(examples, n=2, strategy="recent")
        formatted = format_examples_for_prompt(sample)
        print(f"   Lunghezza output: {len(formatted)} caratteri")
        print(f"   Token stimati: {estimate_tokens(formatted)}")
        print()
        
        print("✅ Tutti i test completati con successo!")
        
    except Exception as e:
        print(f"❌ Errore durante test: {e}")
        import traceback
        traceback.print_exc()

