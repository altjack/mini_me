"""
Flask API server for Daily Report workflow.

Provides REST endpoints for:
- Statistics retrieval
- Email generation
- Draft management
- Approval workflow
- Data backfill

Uses app factory pattern for testability.
"""

import os
from dotenv import load_dotenv

# Carica variabili d'ambiente da .env (se esiste)
load_dotenv()
import sys
import argparse
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional
from functools import wraps

from flask import Flask, jsonify, request, Response
from flask_cors import CORS

# JWT library
try:
    import jwt
except ImportError:
    jwt = None

from workflows.service import DailyReportWorkflow
from workflows.config import ConfigLoader, ConfigurationError
from workflows.logging import LoggerFactory
from workflows.result_types import StepStatus
from ga4_extraction.database import GA4Database
from db_pool import get_pool, close_pool


# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================

import hmac
from collections import defaultdict
from time import time

# Rate limiting per login endpoint (in-memory, per-instance)
# Note: In serverless, each instance has its own state, but this still
# provides protection against rapid brute force within a single instance
LOGIN_ATTEMPTS = defaultdict(list)  # IP -> list of timestamps
MAX_LOGIN_ATTEMPTS = 5  # Max attempts per window
LOGIN_WINDOW_SECONDS = 300  # 5 minute window


def is_rate_limited(ip: str) -> bool:
    """Check if IP is rate limited for login attempts."""
    now = time()
    # Clean old attempts
    LOGIN_ATTEMPTS[ip] = [t for t in LOGIN_ATTEMPTS[ip] if now - t < LOGIN_WINDOW_SECONDS]
    return len(LOGIN_ATTEMPTS[ip]) >= MAX_LOGIN_ATTEMPTS


def record_login_attempt(ip: str):
    """Record a login attempt for rate limiting."""
    LOGIN_ATTEMPTS[ip].append(time())


# Origini CORS permesse (whitelist)
ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:5174',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:5174',
]

# Aggiungi origini da variabile ambiente (per Render/produzione)
# Formato: CORS_ORIGINS=https://example1.com,https://example2.com
if os.getenv('CORS_ORIGINS'):
    ALLOWED_ORIGINS.extend(os.getenv('CORS_ORIGINS').split(','))


# =============================================================================
# APP FACTORY
# =============================================================================

def create_app(config: Optional[dict] = None) -> Flask:
    """
    Application factory per Flask app.
    
    Permette di creare istanze separate per testing.
    
    Args:
        config: Configurazione opzionale (caricata automaticamente se None)
        
    Returns:
        Flask app configurata
    """
    app = Flask(__name__)
    
    # CORS con whitelist origini (SECURITY FIX)
    CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)
    
    # Carica configurazione
    if config is None:
        try:
            config = ConfigLoader.load()
        except ConfigurationError as e:
            print(f"❌ Errore configurazione: {e}")
            sys.exit(1)
    
    # Salva config nell'app context
    app.config['APP_CONFIG'] = config
    
    # Setup logger
    logger = LoggerFactory.get_logger('api', config)
    app.config['LOGGER'] = logger
    
    # Registra routes
    register_routes(app)
    
    # Applica Basic Auth per staging (se configurato)
    apply_basic_auth_to_app(app)
    
    # Inizializza database pool
    db_path = ConfigLoader.get_database_path(config)
    get_pool(db_path, pool_size=10)
    
    # Ritorna connessione al pool dopo ogni request
    @app.teardown_request
    def return_db_to_pool(exception=None):
        """
        Ritorna connessione database al pool dopo ogni request.
        
        Chiama __exit__ sul context manager per chiudere correttamente
        la connessione e ritorna al pool.
        """
        from flask import g
        
        if hasattr(g, 'pool_conn_context') and hasattr(g, 'raw_conn'):
            try:
                # Chiama __exit__ del context manager
                g.pool_conn_context.__exit__(None, None, None)
            except Exception as e:
                logger.error(f"Error returning connection to pool: {e}")
            finally:
                # Cleanup g object
                g.pop('pool_conn_context', None)
                g.pop('raw_conn', None)
                g.pop('db', None)
    
    # Cleanup pool on shutdown
    @app.teardown_appcontext
    def shutdown_pool(exception=None):
        """Chiude connection pool quando app viene terminata."""
        if exception:
            logger.warning(f"App teardown with exception: {exception}")
        close_pool()
    
    return app


# =============================================================================
# HELPERS
# =============================================================================

def get_config():
    """Recupera config da Flask app context"""
    from flask import current_app
    return current_app.config['APP_CONFIG']


def get_logger():
    """Recupera logger da Flask app context"""
    from flask import current_app
    return current_app.config['LOGGER']


def get_db():
    """
    Factory per connessione database con connection pooling.
    
    Usa Flask 'g' object per gestire connessioni per-request.
    Ottiene connessioni dal pool e le ritorna automaticamente al termine.
    
    Returns:
        GA4Database instance con connessione dal pool
    """
    from flask import g
    
    # Check se già abbiamo una connessione per questa request
    if 'db' not in g:
        config = get_config()
        db_path = ConfigLoader.get_database_path(config)
        
        # Ottieni pool (singleton thread-safe)
        pool = get_pool(db_path, pool_size=10)
        
        # Ottieni connessione dal pool usando context manager
        g.pool_conn_context = pool.get_connection()
        g.raw_conn = g.pool_conn_context.__enter__()
        
        # Crea GA4Database con connessione dal pool
        # owns_connection=False perché il pool gestisce il ciclo di vita
        g.db = GA4Database(conn=g.raw_conn, owns_connection=False)
    
    return g.db


def require_api_key(f):
    """
    Decorator per autenticazione API Key.
    
    Richiede header 'X-API-Key' con valore corrispondente 
    alla variabile ambiente API_SECRET_KEY.
    
    Se API_SECRET_KEY non è configurata, l'autenticazione è disabilitata
    (modalità sviluppo).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected_key = os.getenv('API_SECRET_KEY')
        
        # SECURITY: In production, API key MUST be configured
        if not expected_key:
            if os.getenv('VERCEL_ENV') in ('production', 'preview'):
                return jsonify({
                    'success': False,
                    'error': 'Service temporarily unavailable',
                    'error_type': 'config'
                }), 503
            # Dev mode: allow without API key
            return f(*args, **kwargs)
        
        # Verifica API key (constant-time comparison to prevent timing attacks)
        if not api_key or not hmac.compare_digest(api_key.encode(), expected_key.encode()):
            return jsonify({
                'success': False,
                'error': 'Unauthorized - Invalid or missing API key',
                'error_type': 'authentication'
            }), 401
        
        return f(*args, **kwargs)
    return decorated


def require_basic_auth(f):
    """
    Decorator per Basic Authentication (protezione staging).
    
    Richiede header 'Authorization: Basic base64(user:pass)'.
    Credenziali da variabili ambiente STAGING_USER e STAGING_PASSWORD.
    
    Se le variabili non sono configurate, l'autenticazione è disabilitata
    (modalità sviluppo locale).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        staging_user = os.getenv('STAGING_USER')
        staging_password = os.getenv('STAGING_PASSWORD')
        
        # SECURITY: In production, credentials MUST be configured
        if not staging_user or not staging_password:
            if os.getenv('VERCEL_ENV') in ('production', 'preview'):
                return Response(
                    'Service temporarily unavailable',
                    503
                )
            # Dev mode: allow without credentials
            return f(*args, **kwargs)
        
        # Verifica header Authorization
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Basic '):
            return Response(
                'Authentication required',
                401,
                {'WWW-Authenticate': 'Basic realm="Daily Report Staging"'}
            )
        
        # Decodifica credenziali
        try:
            encoded_credentials = auth_header.split(' ', 1)[1]
            decoded = base64.b64decode(encoded_credentials).decode('utf-8')
            username, password = decoded.split(':', 1)
        except (ValueError, UnicodeDecodeError):
            return Response(
                'Invalid authentication format',
                401,
                {'WWW-Authenticate': 'Basic realm="Daily Report Staging"'}
            )
        
        # Verifica credenziali (constant-time comparison to prevent timing attacks)
        import hmac
        username_match = hmac.compare_digest(username.encode(), staging_user.encode())
        password_match = hmac.compare_digest(password.encode(), staging_password.encode())
        if not (username_match and password_match):
            return Response(
                'Invalid credentials',
                401,
                {'WWW-Authenticate': 'Basic realm="Daily Report Staging"'}
            )
        
        return f(*args, **kwargs)
    return decorated


# =============================================================================
# JWT AUTHENTICATION
# =============================================================================

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 30


def get_jwt_secret() -> str:
    """Get JWT secret key from environment.

    SECURITY: In production, JWT_SECRET_KEY MUST be configured.
    Fails closed - no default secret in production.
    """
    secret = os.getenv('JWT_SECRET_KEY')

    # In production/preview, require explicit configuration
    if os.getenv('VERCEL_ENV') in ('production', 'preview'):
        if not secret:
            raise RuntimeError("SECURITY: JWT_SECRET_KEY must be configured in production")
        return secret

    # In development, allow default (with warning)
    if not secret:
        import warnings
        warnings.warn("Using default JWT secret - NOT FOR PRODUCTION", stacklevel=2)
        return 'dev-secret-key-not-for-production'

    return secret


def generate_jwt_token(username: str) -> tuple:
    """Generate a JWT token for the authenticated user."""
    if jwt is None:
        raise RuntimeError("PyJWT library not installed")
    
    secret = get_jwt_secret()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=JWT_EXPIRATION_DAYS)
    
    payload = {
        "sub": username,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp())
    }
    
    token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    return token, expires_at


def verify_jwt_token(token: str) -> Optional[dict]:
    """Verify a JWT token and return payload if valid."""
    if jwt is None:
        return None
    
    try:
        secret = get_jwt_secret()
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def apply_basic_auth_to_app(app: Flask):
    """
    Applica autenticazione a tutti gli endpoint (tranne health check e login).
    
    Accetta sia Basic Auth che JWT Bearer token.
    Chiamare dopo register_routes() per wrappare tutti gli endpoint.
    """
    staging_user = os.getenv('STAGING_USER')
    staging_password = os.getenv('STAGING_PASSWORD')
    
    # Skip se non configurato (dev mode senza auth)
    if not staging_user or not staging_password:
        return
    
    @app.before_request
    def check_auth():
        # Skip health check
        if request.endpoint == 'health_check':
            return None
        
        # Skip login endpoint
        if request.endpoint == 'login':
            return None
        
        # Skip logout endpoint (logout itself will validate)
        if request.endpoint == 'logout':
            return None
        
        # Skip OPTIONS (CORS preflight)
        if request.method == 'OPTIONS':
            return None
        
        # Priority 1: Check HttpOnly cookie (most secure)
        token_from_cookie = request.cookies.get('auth_token')
        if token_from_cookie:
            payload = verify_jwt_token(token_from_cookie)
            if payload:
                return None  # JWT from cookie valid, allow request
        
        # Priority 2: Check Authorization header (fallback for API clients)
        auth_header = request.headers.get('Authorization')
        
        if auth_header:
            # Check JWT Bearer token
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1]
                payload = verify_jwt_token(token)
                if payload:
                    return None  # JWT valid, allow request
                return jsonify({
                    'success': False,
                    'error': 'Invalid or expired token',
                    'error_type': 'authentication'
                }), 401
            
            # Fall back to Basic Auth
            if auth_header.startswith('Basic '):
                try:
                    encoded_credentials = auth_header.split(' ', 1)[1]
                    decoded = base64.b64decode(encoded_credentials).decode('utf-8')
                    username, password = decoded.split(':', 1)
                except (ValueError, UnicodeDecodeError):
                    return Response(
                        'Invalid authentication format',
                        401,
                        {'WWW-Authenticate': 'Basic realm="Daily Report Staging"'}
                    )
                
                if username == staging_user and password == staging_password:
                    return None  # Basic Auth valid
                
                return Response(
                    'Invalid credentials',
                    401,
                    {'WWW-Authenticate': 'Basic realm="Daily Report Staging"'}
                )
        
        # No valid authentication found
        return Response(
            'Authentication required',
            401,
            {'WWW-Authenticate': 'Basic realm="Daily Report Staging"'}
        )


def handle_errors(f):
    """
    Decorator per gestione errori consistente.
    
    Cattura eccezioni e ritorna JSON error response.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ConfigurationError as e:
            get_logger().error(f"Configuration error: {e}")
            return jsonify({
                'success': False,
                'error': 'Configuration error',  # Non esporre dettagli
                'error_type': 'configuration'
            }), 500
        except Exception as e:
            get_logger().error(f"Unexpected error in {f.__name__}: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': 'Internal server error',  # Non esporre dettagli
                'error_type': 'internal'
            }), 500
    return decorated


# =============================================================================
# ROUTES
# =============================================================================

def register_routes(app: Flask):
    """Registra tutti gli endpoint"""
    
    @app.route('/api/auth/login', methods=['POST', 'OPTIONS'])
    def login():
        """
        POST /api/auth/login - Authenticate and set JWT in HttpOnly cookie.
        
        Request body: {"username": "...", "password": "..."}
        Response: {"success": true, "user": "...", "expires_at": "..."}
        
        Security: Token stored in HttpOnly cookie (not accessible via JavaScript)
        """
        if request.method == 'OPTIONS':
            return '', 204

        # Rate limiting check
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown')
        if ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        if is_rate_limited(client_ip):
            return jsonify({
                'success': False,
                'error': 'Too many login attempts. Please try again later.',
                'error_type': 'rate_limit'
            }), 429

        # Check if JWT library is available
        if jwt is None:
            return jsonify({
                'success': False,
                'error': 'JWT library not installed',
                'error_type': 'config'
            }), 503

        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Username and password are required',
                'error_type': 'validation'
            }), 400

        # Get expected credentials
        expected_user = os.getenv('STAGING_USER', 'admin')
        expected_password = os.getenv('STAGING_PASSWORD', 'admin')

        # Verify credentials (constant-time comparison to prevent timing attacks)
        username_match = hmac.compare_digest(username.encode(), expected_user.encode())
        password_match = hmac.compare_digest(password.encode(), expected_password.encode())

        if not (username_match and password_match):
            # Record failed attempt for rate limiting
            record_login_attempt(client_ip)
            return jsonify({
                'success': False,
                'error': 'Invalid username or password',
                'error_type': 'authentication'
            }), 401
        
        # Generate JWT token
        try:
            token, expires_at = generate_jwt_token(username)
        except RuntimeError as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'error_type': 'internal'
            }), 500
        
        # Create response with token in body AND HttpOnly cookie
        # Token in body: for cross-domain deployments (Vercel + separate backend)
        # HttpOnly cookie: for same-domain deployments (more secure)
        response = jsonify({
            'success': True,
            'user': username,
            'token': token,  # Also return token for cross-domain support
            'expires_at': expires_at.isoformat()
        })
        
        # Set HttpOnly cookie with JWT token (works for same-domain)
        # Secure=True in production (HTTPS only), False in development
        is_production = os.getenv('FLASK_ENV') == 'production'
        
        response.set_cookie(
            'auth_token',
            value=token,
            httponly=True,           # Not accessible via JavaScript (XSS protection)
            secure=is_production,    # HTTPS only in production
            samesite='None' if is_production else 'Lax',  # None required for cross-domain
            max_age=JWT_EXPIRATION_DAYS * 24 * 60 * 60,  # 30 days in seconds
            path='/'
        )
        
        return response
    
    @app.route('/api/auth/logout', methods=['POST', 'OPTIONS'])
    def logout():
        """
        POST /api/auth/logout - Clear authentication cookie.
        
        Response: {"success": true, "message": "Logged out successfully"}
        """
        if request.method == 'OPTIONS':
            return '', 204
        
        response = jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })
        
        # Clear the auth cookie
        response.set_cookie(
            'auth_token',
            value='',
            httponly=True,
            secure=os.getenv('FLASK_ENV') == 'production',
            samesite='Lax',
            max_age=0,  # Expire immediately
            path='/'
        )
        
        return response
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """
        Health check endpoint.
        
        Returns:
            200 se servizio OK
        """
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat()
        })
    
    @app.route('/api/stats', methods=['GET'])
    @handle_errors
    def get_stats():
        """
        Statistiche database GA4.
        
        Returns:
            JSON con statistiche aggregate
        """
        db = get_db()
        try:
            stats = db.get_statistics()
            latest_date = db.get_latest_date()
            
            # Backward compatible response for frontend
            return jsonify({
                'record_count': stats.get('record_count', 0),
                'min_date': stats.get('min_date'),
                'max_date': stats.get('max_date'),
                'avg_conversioni': round(stats.get('avg_swi_conversioni', 0), 2),
                'latest_available_date': latest_date
            })
        finally:
            db.close()
    
    @app.route('/api/generate', methods=['POST'])
    @handle_errors
    @require_api_key
    def generate_email():
        """
        Genera draft email (estrazione GA4 + AI Agent).
        
        Request Body (optional):
            {
                "date": "YYYY-MM-DD",    // Data target (default: ieri)
                "force": false           // Forza ri-estrazione
            }
        
        Returns:
            JSON con contenuto draft e metadata
        """
        logger = get_logger()
        config = get_config()
        
        # Parse request body
        data = request.get_json(silent=True) or {}
        target_date = data.get('date')
        force = data.get('force', False)
        
        logger.info(f"Generate request: date={target_date}, force={force}")
        
        # Esegui workflow
        with DailyReportWorkflow(config, logger=logger) as workflow:
            
            # Step 1: Estrazione
            extraction = workflow.run_extraction(
                target_date=target_date,
                force=force
            )
            
            if not extraction.success:
                logger.error(f"Extraction failed: {extraction.error}")
                return jsonify({
                    'success': False,
                    'error': extraction.error or extraction.message,
                    'step': 'extraction'
                }), 500
            
            # Step 2: Generazione
            generation = workflow.run_generation(skip_data_check=True)
            
            if not generation.success:
                logger.error(f"Generation failed: {generation.error}")
                return jsonify({
                    'success': False,
                    'error': generation.error or generation.message,
                    'step': 'generation'
                }), 500
            
            # Leggi contenuto draft
            with open(generation.draft_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Backward compatible response for frontend
            return jsonify({
                'success': True,
                'content': content,
                'data_date': extraction.date
            })
    
    @app.route('/api/draft', methods=['GET'])
    @handle_errors
    def get_draft():
        """
        Legge draft email corrente.
        
        Returns:
            JSON con contenuto draft o exists=false se non presente
        """
        config = get_config()
        draft_path = ConfigLoader.get_draft_path(config)
        
        if not os.path.exists(draft_path):
            return jsonify({'exists': False})
        
        with open(draft_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Backward compatible response for frontend
        return jsonify({
            'exists': True,
            'content': content
        })
    
    @app.route('/api/approve', methods=['POST'])
    @handle_errors
    @require_api_key
    def approve_draft():
        """
        Approva draft corrente (archivia + aggiorna history).
        
        Returns:
            JSON con path archivio
        """
        logger = get_logger()
        config = get_config()
        
        logger.info("Approve request received")
        
        with DailyReportWorkflow(config, logger=logger) as workflow:
            approval = workflow.run_approval(interactive=False)
            
            if approval.success:
                # Backward compatible response for frontend
                return jsonify({
                    'success': True,
                    'archive_path': approval.archive_path
                })
            else:
                status_code = 404 if 'non trovato' in approval.message.lower() else 400
                return jsonify({
                    'success': False,
                    'message': approval.error or approval.message
                }), status_code
    
    @app.route('/api/reject', methods=['POST'])
    @handle_errors
    @require_api_key
    def reject_draft():
        """
        Rifiuta e elimina draft corrente.
        
        Returns:
            JSON con conferma eliminazione
        """
        logger = get_logger()
        config = get_config()
        draft_path = ConfigLoader.get_draft_path(config)
        
        if not os.path.exists(draft_path):
            return jsonify({
                'success': False,
                'error': 'No draft found'
            }), 404
        
        os.remove(draft_path)
        logger.info(f"Draft rejected and deleted: {draft_path}")
        
        return jsonify({
            'success': True,
            'message': 'Draft deleted successfully'
        })
    
    @app.route('/api/backfill', methods=['POST'])
    @handle_errors
    @require_api_key
    def backfill():
        """
        Recupera dati GA4 per range di date.
        
        Request Body:
            {
                "start_date": "YYYY-MM-DD",  // Required
                "end_date": "YYYY-MM-DD",    // Required
                "include_channels": false    // Optional
            }
        
        Returns:
            JSON con risultati per ogni data
        """
        logger = get_logger()
        config = get_config()
        
        data = request.get_json()
        
        # Validazione input
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400
        
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        include_channels = data.get('include_channels', False)
        
        if not start_date_str or not end_date_str:
            return jsonify({
                'success': False,
                'error': 'start_date and end_date are required'
            }), 400
        
        # Parse e valida date
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }), 400
        
        if start_date > end_date:
            return jsonify({
                'success': False,
                'error': 'start_date must be before or equal to end_date'
            }), 400
        
        # Limite ragionevole
        days_diff = (end_date - start_date).days
        if days_diff > 90:
            return jsonify({
                'success': False,
                'error': 'Maximum range is 90 days'
            }), 400
        
        logger.info(f"Backfill request: {start_date_str} to {end_date_str}")
        
        # Calcola data massima per canali (D-2) - GA4 richiede ~48h di ritardo
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        max_channel_date = today - timedelta(days=2)
        
        # Import backfill function
        from scripts.backfill_missing_dates import backfill_single_date
        from ga4_extraction.extraction import extract_sessions_channels_delayed
        
        # Setup risorse
        db = get_db()
        redis_cache = None
        
        try:
            # Tenta connessione Redis (opzionale)
            redis_config = ConfigLoader.get_redis_config(config)
            if redis_config:
                from ga4_extraction.redis_cache import GA4RedisCache
                try:
                    redis_cache = GA4RedisCache(
                        host=redis_config.get('host', 'localhost'),
                        port=redis_config.get('port', 6379),
                        db=redis_config.get('db', 1)
                    )
                except Exception as e:
                    logger.warning(f"Redis not available: {e}")
            
            # Esegui backfill per ogni data
            results = []
            current_date = start_date
            
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                
                try:
                    # Estrai dati principali SENZA canali (gestiti separatamente)
                    success = backfill_single_date(
                        date_str, 
                        db, 
                        redis_cache,
                        include_channels=False  # Canali gestiti sotto con data aggiustata
                    )
                    
                    # Estrai canali solo se richiesto E data <= D-2
                    channels_extracted = False
                    if include_channels and current_date <= max_channel_date:
                        channels_extracted = extract_sessions_channels_delayed(
                            date_str, 
                            db, 
                            skip_validation=True  # Già validato sopra
                        )
                    
                    results.append({
                        'date': date_str,
                        'success': success,
                        'channels_extracted': channels_extracted if include_channels else None,
                        'error': None
                    })
                except Exception as e:
                    logger.error(f"Backfill error for {date_str}: {e}")
                    results.append({
                        'date': date_str,
                        'success': False,
                        'channels_extracted': False if include_channels else None,
                        'error': str(e)
                    })
                
                current_date += timedelta(days=1)
            
            # Calcola statistiche
            success_count = sum(1 for r in results if r['success'])
            channels_count = sum(1 for r in results if r.get('channels_extracted')) if include_channels else 0
            
            return jsonify({
                'success': True,
                'data': {
                    'total': len(results),
                    'successful': success_count,
                    'failed': len(results) - success_count,
                    'channels_extracted': channels_count if include_channels else None,
                    'channels_max_date': max_channel_date.strftime('%Y-%m-%d') if include_channels else None,
                    'details': results
                }
            })
            
        finally:
            db.close()
            if redis_cache:
                redis_cache.close()
    
    @app.route('/api/workflow/full', methods=['POST'])
    @handle_errors
    @require_api_key
    def run_full_workflow():
        """
        Esegue workflow completo: Extract → Generate → Approve
        
        Request Body (optional):
            {
                "date": "YYYY-MM-DD",
                "force": false,
                "auto_approve": true  // Required for non-interactive
            }
        
        Returns:
            JSON con risultati di tutti gli step
        """
        logger = get_logger()
        config = get_config()
        
        data = request.get_json(silent=True) or {}
        target_date = data.get('date')
        force = data.get('force', False)
        auto_approve = data.get('auto_approve', True)
        
        logger.info(f"Full workflow request: date={target_date}, force={force}, auto_approve={auto_approve}")
        
        with DailyReportWorkflow(config, logger=logger) as workflow:
            result = workflow.run_full(
                target_date=target_date,
                force_extraction=force,
                auto_approve=auto_approve
            )
            
            # Costruisci risposta
            steps_data = []
            for step in result.steps:
                step_data = {
                    'status': step.status.name,
                    'message': step.message,
                    'success': step.success
                }
                if step.error:
                    step_data['error'] = step.error
                
                # Aggiungi attributi specifici per tipo
                if hasattr(step, 'date') and step.date:
                    step_data['date'] = step.date
                if hasattr(step, 'draft_path') and step.draft_path:
                    step_data['draft_path'] = step.draft_path
                if hasattr(step, 'archive_path') and step.archive_path:
                    step_data['archive_path'] = step.archive_path
                
                steps_data.append(step_data)
            
            return jsonify({
                'success': result.success,
                'data': {
                    'steps': steps_data,
                    'duration_seconds': round(result.duration_seconds, 2),
                    'errors': result.errors
                }
            })
    
    @app.route('/api/metrics/range', methods=['GET'])
    @handle_errors
    def get_metrics_range():
        """
        Recupera metriche per un range di date (per dashboard).
        
        Query Parameters:
            start_date: Data inizio (YYYY-MM-DD), default: 45 giorni fa
            end_date: Data fine (YYYY-MM-DD), default: ieri
        
        Returns:
            JSON con lista di metriche giornaliere incluso flag weekend
        """
        # Parse parametri con default a ultimi 45 giorni
        end_date_str = request.args.get('end_date')
        start_date_str = request.args.get('start_date')
        
        # Default: ultimi 45 giorni fino a ieri
        if not end_date_str:
            end_date = datetime.now() - timedelta(days=1)
            end_date_str = end_date.strftime('%Y-%m-%d')
        else:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        if not start_date_str:
            start_date = end_date - timedelta(days=44)  # 45 giorni totali
            start_date_str = start_date.strftime('%Y-%m-%d')
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        
        # Validazione
        if start_date > end_date:
            return jsonify({
                'success': False,
                'error': 'start_date must be before or equal to end_date'
            }), 400
        
        # Limite massimo 90 giorni
        days_diff = (end_date - start_date).days
        if days_diff > 90:
            return jsonify({
                'success': False,
                'error': 'Maximum range is 90 days'
            }), 400
        
        db = get_db()
        try:
            metrics = db.get_date_range(start_date_str, end_date_str)
            
            # Arricchisci con flag weekend, dati CR e formatta per frontend
            result = []
            for m in metrics:
                date_obj = datetime.strptime(m['date'], '%Y-%m-%d')
                is_weekend = date_obj.weekday() >= 5  # Sabato=5, Domenica=6
                
                result.append({
                    'date': m['date'],
                    'swi': m['swi_conversioni'],
                    'cr_commodity': m['cr_commodity'],
                    'cr_lucegas': m['cr_lucegas'],
                    'isWeekend': is_weekend
                })
            
            # Calcola medie per linee di riferimento
            swi_values = [r['swi'] for r in result if r['swi'] is not None]
            avg_swi = round(sum(swi_values) / len(swi_values), 2) if swi_values else 0
            
            cr_commodity_values = [r['cr_commodity'] for r in result if r['cr_commodity'] is not None]
            avg_cr_commodity = round(sum(cr_commodity_values) / len(cr_commodity_values), 2) if cr_commodity_values else 0
            
            cr_lucegas_values = [r['cr_lucegas'] for r in result if r['cr_lucegas'] is not None]
            avg_cr_lucegas = round(sum(cr_lucegas_values) / len(cr_lucegas_values), 2) if cr_lucegas_values else 0
            
            return jsonify({
                'success': True,
                'data': result,
                'meta': {
                    'start_date': start_date_str,
                    'end_date': end_date_str,
                    'count': len(result),
                    'average': avg_swi,
                    'avg_cr_commodity': avg_cr_commodity,
                    'avg_cr_lucegas': avg_cr_lucegas
                }
            })
        finally:
            db.close()
    
    @app.route('/api/sessions/range', methods=['GET'])
    @handle_errors
    def get_sessions_range():
        """
        Recupera sessioni (totali e per canale) per un range di date.
        
        Query Parameters:
            start_date: Data inizio (YYYY-MM-DD), default: 45 giorni fa
            end_date: Data fine (YYYY-MM-DD), default: ieri
        
        Returns:
            JSON con totali giornalieri e breakdown per canale
        """
        # Parse parametri (stessa logica di metrics/range)
        end_date_str = request.args.get('end_date')
        start_date_str = request.args.get('start_date')
        
        if not end_date_str:
            end_date = datetime.now() - timedelta(days=1)
            end_date_str = end_date.strftime('%Y-%m-%d')
        else:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        if not start_date_str:
            start_date = end_date - timedelta(days=44)
            start_date_str = start_date.strftime('%Y-%m-%d')
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        
        if start_date > end_date:
            return jsonify({
                'success': False,
                'error': 'start_date must be before or equal to end_date'
            }), 400
        
        days_diff = (end_date - start_date).days
        if days_diff > 90:
            return jsonify({
                'success': False,
                'error': 'Maximum range is 90 days'
            }), 400
        
        # Canali di interesse
        TARGET_CHANNELS = ['Paid Media e Display', 'Organic Search', 'Direct', 'Paid Search']
        
        db = get_db()
        try:
            # Recupera metriche totali giornaliere
            metrics = db.get_date_range(start_date_str, end_date_str)
            
            # Costruisci totali
            totals = []
            for m in metrics:
                totals.append({
                    'date': m['date'],
                    'commodity': m['sessioni_commodity'],
                    'lucegas': m['sessioni_lucegas']
                })
            
            # Recupera sessioni per canale
            by_channel = []
            cursor = db.conn.cursor()
            cursor.execute("""
                SELECT date, channel, commodity_sessions, lucegas_sessions
                FROM sessions_by_channel
                WHERE date BETWEEN ? AND ?
                AND channel IN (?, ?, ?, ?)
                ORDER BY date ASC, channel
            """, (start_date_str, end_date_str, *TARGET_CHANNELS))
            
            for row in cursor.fetchall():
                by_channel.append({
                    'date': row['date'],
                    'channel': row['channel'],
                    'commodity': row['commodity_sessions'],
                    'lucegas': row['lucegas_sessions']
                })
            
            return jsonify({
                'success': True,
                'data': {
                    'totals': totals,
                    'by_channel': by_channel
                },
                'meta': {
                    'start_date': start_date_str,
                    'end_date': end_date_str,
                    'count': len(totals),
                    'channels': TARGET_CHANNELS
                }
            })
        finally:
            db.close()


# =============================================================================
# MAIN
# =============================================================================

# Create app instance for direct execution
app = create_app()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Daily Report API Server')
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=5001,
        help='Port to run server on (default: 5001)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )
    args = parser.parse_args()
    
    print(f"🚀 Starting API server on {args.host}:{args.port}...")
    app.run(host=args.host, port=args.port, debug=args.debug)
