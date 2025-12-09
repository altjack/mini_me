"""
Utilities condivise per Vercel Serverless Functions.

Fornisce:
- Connessione database PostgreSQL
- Basic Auth middleware
- CORS headers
- JSON response helpers
"""

import os
import json
import base64
import sys
from typing import Optional, Dict, Any, Callable
from functools import wraps
from http.server import BaseHTTPRequestHandler

# Aggiungi root al path per importare moduli del progetto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# DATABASE
# =============================================================================

def get_db():
    """
    Factory per connessione database PostgreSQL.
    Usa DATABASE_URL da environment variables.
    """
    from ga4_extraction.database import GA4Database
    return GA4Database()


# =============================================================================
# CORS HEADERS
# =============================================================================

def get_cors_headers() -> Dict[str, str]:
    """
    Restituisce headers CORS per le risposte.
    Permette origini da CORS_ORIGINS env var o localhost per dev.
    """
    allowed_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5173')
    
    return {
        'Access-Control-Allow-Origin': allowed_origins,
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-API-Key',
        'Access-Control-Allow-Credentials': 'true',
    }


# =============================================================================
# JSON RESPONSES
# =============================================================================

def json_response(data: Any, status: int = 200) -> Dict:
    """
    Crea una risposta JSON per Vercel.
    
    Args:
        data: Dati da serializzare in JSON
        status: HTTP status code
    
    Returns:
        Dict con statusCode, headers, body
    """
    headers = get_cors_headers()
    headers['Content-Type'] = 'application/json'
    
    return {
        'statusCode': status,
        'headers': headers,
        'body': json.dumps(data, default=str)
    }


def error_response(message: str, status: int = 400, error_type: str = 'error') -> Dict:
    """
    Crea una risposta di errore JSON.
    """
    return json_response({
        'success': False,
        'error': message,
        'error_type': error_type
    }, status)


def options_response() -> Dict:
    """
    Risposta per preflight CORS (OPTIONS request).
    """
    return {
        'statusCode': 204,
        'headers': get_cors_headers(),
        'body': ''
    }


# =============================================================================
# BASIC AUTH
# =============================================================================

def check_basic_auth(request) -> Optional[Dict]:
    """
    Verifica Basic Auth dalle headers della request.
    
    Args:
        request: Vercel request object
    
    Returns:
        None se auth OK, altrimenti error response dict
    """
    staging_user = os.getenv('STAGING_USER')
    staging_password = os.getenv('STAGING_PASSWORD')
    
    # Se non configurato, skip auth (dev mode)
    if not staging_user or not staging_password:
        return None
    
    # Ottieni Authorization header
    auth_header = request.headers.get('Authorization', '')
    
    if not auth_header or not auth_header.startswith('Basic '):
        return {
            'statusCode': 401,
            'headers': {
                **get_cors_headers(),
                'WWW-Authenticate': 'Basic realm="Daily Report Staging"'
            },
            'body': 'Authentication required'
        }
    
    # Decodifica credenziali
    try:
        encoded = auth_header.split(' ', 1)[1]
        decoded = base64.b64decode(encoded).decode('utf-8')
        username, password = decoded.split(':', 1)
    except (ValueError, UnicodeDecodeError):
        return {
            'statusCode': 401,
            'headers': {
                **get_cors_headers(),
                'WWW-Authenticate': 'Basic realm="Daily Report Staging"'
            },
            'body': 'Invalid authentication format'
        }
    
    # Verifica credenziali
    if username != staging_user or password != staging_password:
        return {
            'statusCode': 401,
            'headers': {
                **get_cors_headers(),
                'WWW-Authenticate': 'Basic realm="Daily Report Staging"'
            },
            'body': 'Invalid credentials'
        }
    
    return None  # Auth OK


def check_api_key(request) -> Optional[Dict]:
    """
    Verifica API Key per endpoint protetti.
    
    Args:
        request: Vercel request object
    
    Returns:
        None se auth OK, altrimenti error response dict
    """
    expected_key = os.getenv('API_SECRET_KEY')
    
    # Se non configurato, skip (dev mode)
    if not expected_key:
        return None
    
    api_key = request.headers.get('X-API-Key', '')
    
    if api_key != expected_key:
        return error_response('Unauthorized - Invalid or missing API key', 401, 'authentication')
    
    return None


# =============================================================================
# REQUEST HELPERS
# =============================================================================

def get_query_param(request, name: str, default: str = None) -> Optional[str]:
    """
    Ottiene un query parameter dalla request.
    """
    # Vercel passa i query params in request.args o request.query
    if hasattr(request, 'args'):
        return request.args.get(name, default)
    elif hasattr(request, 'query'):
        return request.query.get(name, default)
    return default


def get_json_body(request) -> Optional[Dict]:
    """
    Ottiene il body JSON dalla request.
    """
    try:
        if hasattr(request, 'body'):
            body = request.body
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            if body:
                return json.loads(body)
        elif hasattr(request, 'json'):
            return request.json
    except (json.JSONDecodeError, Exception):
        pass
    return None


# =============================================================================
# CONFIG LOADER (semplificato per serverless)
# =============================================================================

def get_config() -> Dict:
    """
    Carica configurazione minima per serverless.
    """
    return {
        'database': {
            'sqlite': {
                'path': 'data/ga4_data.db'  # Fallback locale
            }
        },
        'execution': {
            'output_dir': '/tmp/email',  # Vercel usa /tmp per file temporanei
            'draft_filename': 'draft_email.md',
            'archive_dir': '/tmp/email/archive'
        }
    }


def get_draft_path() -> str:
    """Path del draft email (usa /tmp su Vercel)."""
    return '/tmp/email/draft_email.md'


def get_archive_dir() -> str:
    """Path directory archivio."""
    return '/tmp/email/archive'


# =============================================================================
# DECORATORS
# =============================================================================

def with_cors(handler: Callable) -> Callable:
    """
    Decorator per gestire CORS automaticamente.
    Risponde a OPTIONS e aggiunge headers CORS.
    """
    @wraps(handler)
    def wrapper(request):
        # Handle OPTIONS preflight
        if request.method == 'OPTIONS':
            return options_response()
        
        # Call handler
        response = handler(request)
        
        # Ensure CORS headers
        if isinstance(response, dict) and 'headers' in response:
            response['headers'] = {**get_cors_headers(), **response['headers']}
        
        return response
    
    return wrapper


def with_auth(handler: Callable) -> Callable:
    """
    Decorator per richiedere Basic Auth.
    """
    @wraps(handler)
    def wrapper(request):
        # Check auth
        auth_error = check_basic_auth(request)
        if auth_error:
            return auth_error
        
        return handler(request)
    
    return wrapper


def with_api_key(handler: Callable) -> Callable:
    """
    Decorator per richiedere API Key (per POST protetti).
    """
    @wraps(handler)
    def wrapper(request):
        # Check API key
        auth_error = check_api_key(request)
        if auth_error:
            return auth_error
        
        return handler(request)
    
    return wrapper

