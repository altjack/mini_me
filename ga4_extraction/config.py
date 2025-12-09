import json
import tempfile
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv
import os 
import sys
import logging

# Usa /tmp su Vercel (filesystem read-only), altrimenti directory corrente
LOG_PATH = '/tmp/ga4_extraction.log' if os.getenv('VERCEL') else 'ga4_extraction.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']
PROPERTY_ID = os.getenv('PROPERTY_ID')


def get_credentials_from_env() -> Credentials:
    """
    Carica credenziali OAuth da variabile ambiente (per deploy cloud).
    
    La variabile GOOGLE_CREDENTIALS_JSON deve contenere il JSON
    del token OAuth (contenuto di token.json).
    """
    creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
    if not creds_json:
        return None
    
    try:
        creds_data = json.loads(creds_json)
        creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
        
        # Refresh se necessario
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refresh token in corso (from env)...")
            creds.refresh(Request())
        
        return creds
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Errore parsing GOOGLE_CREDENTIALS_JSON: {e}")
        return None


def get_credentials() -> Credentials:
    """
    Gestisce autenticazione OAuth con refresh automatico.
    
    Ordine di priorità:
    1. Variabile ambiente GOOGLE_CREDENTIALS_JSON (per cloud/Render)
    2. File credentials/token.json (per sviluppo locale)
    """
    creds = None
    
    # Prima prova variabile ambiente (per deploy cloud)
    creds = get_credentials_from_env()
    if creds and creds.valid:
        logger.info("Credenziali caricate da variabile ambiente")
        return creds
    
    # Fallback a file locale
    if os.path.exists('credentials/token.json'):
        creds = Credentials.from_authorized_user_file('credentials/token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refresh token in corso...")
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials/credentials.json'):
                logger.error("File credentials/credentials.json non trovato!")
                logger.error("Scaricalo da Google Cloud Console")
                logger.error("Oppure configura GOOGLE_CREDENTIALS_JSON per deploy cloud")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials/credentials.json', 
                scopes=SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Salva credenziali per esecuzioni future (solo se directory esiste)
        if os.path.exists('credentials'):
            with open('credentials/token.json', 'w') as token:
                token.write(creds.to_json())
    
    return creds