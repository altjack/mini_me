"""
Utilities condivise per Vercel Serverless Functions.

Fornisce:
- Connessione database PostgreSQL
- Basic Auth middleware (SICURO in produzione)
- CORS headers
- JSON response helpers
- Error sanitization

SECURITY NOTES:
- In produzione (VERCEL_ENV=production), l'autenticazione è OBBLIGATORIA
- I messaggi di errore sono sanitizzati per non esporre dettagli interni
- CORS è configurato con origini specifiche, MAI wildcard
"""

import os
import json
import base64
import sys
import logging
from typing import Optional, Dict, Any, Callable
from functools import wraps
from http.server import BaseHTTPRequestHandler

# JWT library (optional import)
try:
    import jwt
except ImportError:
    jwt = None

# Aggiungi root al path per importare moduli del progetto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Logger per debug interno (non esposto agli utenti)
logger = logging.getLogger(__name__)


# =============================================================================
# ENVIRONMENT HELPERS
# =============================================================================

def is_production() -> bool:
    """Verifica se siamo in ambiente di produzione Vercel."""
    return os.getenv('VERCEL_ENV') == 'production'


def is_preview() -> bool:
    """Verifica se siamo in ambiente preview/staging Vercel."""
    return os.getenv('VERCEL_ENV') == 'preview'


def is_development() -> bool:
    """Verifica se siamo in ambiente di sviluppo locale."""
    return not os.getenv('VERCEL')


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
# CORS HEADERS (SECURED)
# =============================================================================

# Origini CORS permesse (whitelist esplicita)
DEFAULT_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:5174',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:5174',
]


def get_allowed_origins() -> list:
    """
    Restituisce lista di origini CORS permesse.
    
    Legge da CORS_ORIGINS env var (comma-separated) o usa default per dev.
    MAI ritorna '*' (wildcard).
    """
    cors_origins_env = os.getenv('CORS_ORIGINS', '')
    
    if cors_origins_env:
        # Parse comma-separated origins
        origins = [o.strip() for o in cors_origins_env.split(',') if o.strip()]
        # Filtra eventuali wildcard (sicurezza)
        origins = [o for o in origins if o != '*']
        return origins if origins else DEFAULT_ALLOWED_ORIGINS
    
    return DEFAULT_ALLOWED_ORIGINS


def get_cors_headers(request_origin: Optional[str] = None) -> Dict[str, str]:
    """
    Restituisce headers CORS per le risposte.
    
    Args:
        request_origin: Origin header dalla request (opzionale)
    
    Returns:
        Dict con headers CORS sicuri
    
    SECURITY:
    - MAI usa '*' come origin
    - Verifica che l'origin sia nella whitelist
    - Allow-Credentials solo se origin specifico
    """
    allowed_origins = get_allowed_origins()
    
    # Determina l'origin da usare nella risposta
    if request_origin and request_origin in allowed_origins:
        response_origin = request_origin
        allow_credentials = 'true'
    elif len(allowed_origins) == 1:
        # Se c'è solo un'origine, usala
        response_origin = allowed_origins[0]
        allow_credentials = 'true'
    else:
        # Fallback: usa la prima origine, no credentials
        response_origin = allowed_origins[0] if allowed_origins else 'http://localhost:5173'
        allow_credentials = 'false'
    
    return {
        'Access-Control-Allow-Origin': response_origin,
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-API-Key',
        'Access-Control-Allow-Credentials': allow_credentials,
        'Access-Control-Max-Age': '86400',  # Cache preflight per 24h
    }


# =============================================================================
# JSON RESPONSES
# =============================================================================

def json_response(data: Any, status: int = 200, request_origin: Optional[str] = None) -> Dict:
    """
    Crea una risposta JSON per Vercel.
    
    Args:
        data: Dati da serializzare in JSON
        status: HTTP status code
        request_origin: Origin dalla request per CORS
    
    Returns:
        Dict con statusCode, headers, body
    """
    headers = get_cors_headers(request_origin)
    headers['Content-Type'] = 'application/json'
    
    return {
        'statusCode': status,
        'headers': headers,
        'body': json.dumps(data, default=str)
    }


def error_response(
    message: str, 
    status: int = 400, 
    error_type: str = 'error',
    internal_message: Optional[str] = None,
    request_origin: Optional[str] = None
) -> Dict:
    """
    Crea una risposta di errore JSON SICURA.
    
    Args:
        message: Messaggio user-facing (SANITIZZATO)
        status: HTTP status code
        error_type: Tipo errore per categorizzazione
        internal_message: Messaggio per logging interno (MAI esposto)
        request_origin: Origin dalla request per CORS
    
    SECURITY:
    - Il messaggio esposto NON contiene dettagli interni
    - internal_message viene solo loggato, mai restituito
    """
    # Log dettagliato internamente
    if internal_message:
        logger.error(f"[{error_type}] {internal_message}")
    
    return json_response({
        'success': False,
        'error': message,
        'error_type': error_type
    }, status, request_origin)


def options_response(request_origin: Optional[str] = None) -> Dict:
    """
    Risposta per preflight CORS (OPTIONS request).
    """
    return {
        'statusCode': 204,
        'headers': get_cors_headers(request_origin),
        'body': ''
    }


# =============================================================================
# SANITIZED ERROR MESSAGES
# =============================================================================

# Mapping errori interni -> messaggi user-facing
SAFE_ERROR_MESSAGES = {
    'database': 'A database error occurred. Please try again later.',
    'extraction': 'Data extraction failed. Please try again later.',
    'generation': 'Report generation failed. Please try again later.',
    'validation': None,  # Usa messaggio originale (sono già user-facing)
    'authentication': None,  # Usa messaggio originale
    'internal': 'An internal error occurred. Please try again later.',
    'config': 'Service configuration error. Please contact support.',
}


def safe_error_response(
    error_type: str,
    internal_error: Exception,
    user_message: Optional[str] = None,
    status: int = 500,
    request_origin: Optional[str] = None
) -> Dict:
    """
    Crea una risposta di errore SICURA che non espone dettagli interni.
    
    Args:
        error_type: Tipo di errore (database, extraction, etc.)
        internal_error: Eccezione originale (per logging)
        user_message: Messaggio user-facing opzionale
        status: HTTP status code
        request_origin: Origin dalla request per CORS
    
    Returns:
        Risposta errore con messaggio sanitizzato
    """
    # Determina messaggio user-facing
    safe_message = user_message or SAFE_ERROR_MESSAGES.get(error_type, 'An error occurred.')
    
    # Log errore completo internamente
    logger.error(
        f"[{error_type}] Internal error: {type(internal_error).__name__}: {internal_error}",
        exc_info=True
    )
    
    return error_response(
        message=safe_message,
        status=status,
        error_type=error_type,
        internal_message=str(internal_error),
        request_origin=request_origin
    )


# =============================================================================
# BASIC AUTH (SECURED)
# =============================================================================

def check_basic_auth(request) -> Optional[Dict]:
    """
    Verifica Basic Auth dalle headers della request.
    
    Args:
        request: Vercel request object
    
    Returns:
        None se auth OK, altrimenti error response dict
    
    SECURITY:
    - In PRODUZIONE, fallisce se credenziali non configurate
    - In development, permette accesso senza auth (per testing)
    """
    staging_user = os.getenv('STAGING_USER')
    staging_password = os.getenv('STAGING_PASSWORD')
    request_origin = request.headers.get('Origin', '')
    
    # SECURITY: In produzione/preview, le credenziali DEVONO essere configurate
    if (is_production() or is_preview()) and (not staging_user or not staging_password):
        logger.critical("SECURITY: Auth credentials not configured in production!")
        return error_response(
            message='Service temporarily unavailable',
            status=503,
            error_type='config',
            internal_message='STAGING_USER/STAGING_PASSWORD not configured in production',
            request_origin=request_origin
        )
    
    # In development locale senza credenziali, permetti (dev mode)
    if is_development() and (not staging_user or not staging_password):
        return None
    
    # Ottieni Authorization header
    auth_header = request.headers.get('Authorization', '')
    
    if not auth_header or not auth_header.startswith('Basic '):
        return {
            'statusCode': 401,
            'headers': {
                **get_cors_headers(request_origin),
                'WWW-Authenticate': 'Basic realm="Daily Report"'
            },
            'body': 'Authentication required'
        }
    
    # Decodifica credenziali
    try:
        encoded = auth_header.split(' ', 1)[1]
        decoded = base64.b64decode(encoded).decode('utf-8')
        username, password = decoded.split(':', 1)
    except (ValueError, UnicodeDecodeError, IndexError):
        logger.warning(f"Invalid auth format from {request.headers.get('X-Forwarded-For', 'unknown')}")
        return {
            'statusCode': 401,
            'headers': {
                **get_cors_headers(request_origin),
                'WWW-Authenticate': 'Basic realm="Daily Report"'
            },
            'body': 'Invalid authentication format'
        }
    
    # Verifica credenziali (timing-safe comparison sarebbe ideale)
    if username != staging_user or password != staging_password:
        logger.warning(f"Invalid credentials attempt from {request.headers.get('X-Forwarded-For', 'unknown')}")
        return {
            'statusCode': 401,
            'headers': {
                **get_cors_headers(request_origin),
                'WWW-Authenticate': 'Basic realm="Daily Report"'
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
    
    SECURITY:
    - In PRODUZIONE, la API key DEVE essere configurata
    - In development, permette accesso senza API key
    """
    expected_key = os.getenv('API_SECRET_KEY')
    request_origin = request.headers.get('Origin', '')
    
    # SECURITY: In produzione, API key DEVE essere configurata
    if (is_production() or is_preview()) and not expected_key:
        logger.critical("SECURITY: API_SECRET_KEY not configured in production!")
        return error_response(
            message='Service temporarily unavailable',
            status=503,
            error_type='config',
            internal_message='API_SECRET_KEY not configured in production',
            request_origin=request_origin
        )
    
    # In development senza API key, permetti
    if is_development() and not expected_key:
        return None
    
    api_key = request.headers.get('X-API-Key', '')
    
    if api_key != expected_key:
        logger.warning(f"Invalid API key attempt from {request.headers.get('X-Forwarded-For', 'unknown')}")
        return error_response(
            message='Unauthorized - Invalid or missing API key',
            status=401,
            error_type='authentication',
            request_origin=request_origin
        )
    
    return None


# =============================================================================
# JWT AUTHENTICATION
# =============================================================================

JWT_ALGORITHM = "HS256"


def get_jwt_secret() -> str:
    """Get JWT secret key from environment."""
    return os.getenv('JWT_SECRET_KEY', '')


def check_jwt_auth(request) -> Optional[Dict]:
    """
    Verifica JWT token per endpoint protetti.
    
    Args:
        request: Vercel request object (con headers)
    
    Returns:
        None se auth OK, altrimenti error response dict
    
    SECURITY:
    - In PRODUZIONE, JWT_SECRET_KEY DEVE essere configurata
    - In development, permette accesso senza token (per testing)
    - Verifica signature e expiration del token
    """
    request_origin = request.headers.get('Origin', '')
    
    # Check if JWT library is available
    if jwt is None:
        logger.error("PyJWT library not installed")
        return error_response(
            message='Authentication service unavailable',
            status=503,
            error_type='config',
            internal_message='PyJWT library not installed',
            request_origin=request_origin
        )
    
    jwt_secret = get_jwt_secret()
    
    # SECURITY: In produzione, JWT secret DEVE essere configurata
    if (is_production() or is_preview()) and not jwt_secret:
        logger.critical("SECURITY: JWT_SECRET_KEY not configured in production!")
        return error_response(
            message='Service temporarily unavailable',
            status=503,
            error_type='config',
            internal_message='JWT_SECRET_KEY not configured in production',
            request_origin=request_origin
        )
    
    # In development senza JWT secret, permetti (dev mode)
    if is_development() and not jwt_secret:
        return None
    
    # Ottieni Authorization header
    auth_header = request.headers.get('Authorization', '')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return error_response(
            message='Authorization token required',
            status=401,
            error_type='authentication',
            request_origin=request_origin
        )
    
    # Estrai token
    try:
        token = auth_header.split(' ', 1)[1]
    except IndexError:
        return error_response(
            message='Invalid authorization header format',
            status=401,
            error_type='authentication',
            request_origin=request_origin
        )
    
    # Verifica e decodifica token
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=[JWT_ALGORITHM])
        
        # Token valido - opzionalmente possiamo salvare info utente nella request
        # request.jwt_user = payload.get('sub')
        
        logger.debug(f"JWT auth successful for user: {payload.get('sub')}")
        return None  # Auth OK
        
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return error_response(
            message='Token expired - please login again',
            status=401,
            error_type='authentication',
            request_origin=request_origin
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return error_response(
            message='Invalid token - please login again',
            status=401,
            error_type='authentication',
            request_origin=request_origin
        )


def with_jwt_auth(handler: Callable) -> Callable:
    """
    Decorator per richiedere JWT authentication.
    """
    @wraps(handler)
    def wrapper(request):
        # Check JWT auth
        auth_error = check_jwt_auth(request)
        if auth_error:
            return auth_error
        
        return handler(request)
    
    return wrapper


# =============================================================================
# INPUT VALIDATION
# =============================================================================

def validate_date_string(date_str: str, field_name: str = 'date') -> Optional[str]:
    """
    Valida una stringa data nel formato YYYY-MM-DD.
    
    Args:
        date_str: Stringa da validare
        field_name: Nome campo per messaggi di errore
    
    Returns:
        None se valida, messaggio di errore altrimenti
    """
    from datetime import datetime
    
    if not date_str:
        return f'{field_name} is required'
    
    # Verifica formato
    try:
        parsed = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return f'{field_name} must be in YYYY-MM-DD format'
    
    # Verifica range ragionevole (non nel futuro, non troppo vecchia)
    now = datetime.now()
    min_date = datetime(2020, 1, 1)
    
    if parsed > now:
        return f'{field_name} cannot be in the future'
    
    if parsed < min_date:
        return f'{field_name} cannot be before 2020-01-01'
    
    return None  # Valida


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
        request_origin = request.headers.get('Origin', '') if hasattr(request, 'headers') else ''
        
        # Handle OPTIONS preflight
        if hasattr(request, 'method') and request.method == 'OPTIONS':
            return options_response(request_origin)
        
        # Call handler
        response = handler(request)
        
        # Ensure CORS headers
        if isinstance(response, dict) and 'headers' in response:
            response['headers'] = {**get_cors_headers(request_origin), **response['headers']}
        
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
