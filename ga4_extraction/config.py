
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv
import os 
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ga4_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']
PROPERTY_ID = os.getenv('PROPERTY_ID')

def get_credentials() -> Credentials:
    """
    Gestisce autenticazione OAuth con refresh automatico
    """
    creds = None
    
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
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials/credentials.json', 
                scopes=SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Salva credenziali per esecuzioni future
        with open('credentials/token.json', 'w') as token:
            token.write(creds.to_json())
    
    return creds