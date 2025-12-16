"""
Login Endpoint - POST /api/auth/login

Autentica utente e genera JWT token.
Verifica credenziali vs STAGING_USER/STAGING_PASSWORD.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hmac
import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
import logging

# Import JWT library
try:
    import jwt
except ImportError:
    jwt = None

from _utils import (
    json_response, error_response, options_response,
    get_cors_headers, is_production, is_preview, is_development
)

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 30

# Rate limiting configuration
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 minutes

# In-memory rate limiting (per-instance, limited effectiveness in serverless)
# For production, consider using Vercel KV or Redis
from collections import defaultdict
from time import time
_login_attempts = defaultdict(list)


def is_rate_limited(ip: str) -> bool:
    """Check if IP is rate limited for login attempts."""
    now = time()
    # Clean old attempts
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < LOGIN_WINDOW_SECONDS]
    return len(_login_attempts[ip]) >= MAX_LOGIN_ATTEMPTS


def record_login_attempt(ip: str):
    """Record a failed login attempt for rate limiting."""
    _login_attempts[ip].append(time())


def get_jwt_secret() -> str:
    """Get JWT secret key from environment."""
    return os.getenv('JWT_SECRET_KEY', '')


def generate_jwt_token(username: str) -> tuple[str, datetime]:
    """
    Generate a JWT token for the authenticated user.
    
    Args:
        username: The authenticated username
        
    Returns:
        Tuple of (token_string, expiration_datetime)
    """
    if jwt is None:
        raise RuntimeError("PyJWT library not installed")
    
    secret = get_jwt_secret()
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY not configured")
    
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=JWT_EXPIRATION_DAYS)
    
    payload = {
        "sub": username,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp())
    }
    
    token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    
    return token, expires_at


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for login."""
    
    def do_POST(self):
        """POST /api/auth/login - Authenticate user and return JWT."""
        request_origin = self.headers.get('Origin', '')

        # Get client IP for rate limiting
        client_ip = self.headers.get('X-Forwarded-For', self.client_address[0] if self.client_address else 'unknown')
        if ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        # Rate limiting check
        if is_rate_limited(client_ip):
            response = error_response(
                message='Too many login attempts. Please try again later.',
                status=429,
                error_type='rate_limit',
                request_origin=request_origin
            )
            self._send_response(response)
            return

        # Check if JWT library is available
        if jwt is None:
            response = error_response(
                message='Authentication service unavailable',
                status=503,
                error_type='config',
                internal_message='PyJWT library not installed',
                request_origin=request_origin
            )
            self._send_response(response)
            return
        
        # Check if JWT secret is configured (required in production/preview)
        jwt_secret = get_jwt_secret()
        if (is_production() or is_preview()) and not jwt_secret:
            logger.critical("SECURITY: JWT_SECRET_KEY not configured in production!")
            response = error_response(
                message='Service temporarily unavailable',
                status=503,
                error_type='config',
                internal_message='JWT_SECRET_KEY not configured',
                request_origin=request_origin
            )
            self._send_response(response)
            return
        
        # In development without JWT secret, use a default (NOT for production!)
        if is_development() and not jwt_secret:
            os.environ['JWT_SECRET_KEY'] = 'dev-secret-key-not-for-production'
        
        try:
            # Parse request body - handle Vercel serverless quirks
            content_length = int(self.headers.get('Content-Length', 0))
            
            # Try to read body
            if content_length > 0:
                body = self.rfile.read(content_length)
            else:
                # Vercel might not set Content-Length, try reading anyway
                try:
                    body = self.rfile.read()
                except Exception:
                    body = b'{}'
            
            # Parse JSON
            if body:
                data = json.loads(body.decode('utf-8'))
            else:
                data = {}
            
            # Debug logging
            logger.info(f"Login request: content_length={content_length}, body_len={len(body) if body else 0}")
            
            username = data.get('username', '').strip()
            password = data.get('password', '')
            
            # Validate input
            if not username or not password:
                response = error_response(
                    message='Username and password are required',
                    status=400,
                    error_type='validation',
                    request_origin=request_origin
                )
                self._send_response(response)
                return
            
            # Get expected credentials from environment
            expected_user = os.getenv('STAGING_USER', '')
            expected_password = os.getenv('STAGING_PASSWORD', '')
            
            # In production/preview, credentials must be configured
            if (is_production() or is_preview()) and (not expected_user or not expected_password):
                logger.critical("SECURITY: Auth credentials not configured in production!")
                response = error_response(
                    message='Service temporarily unavailable',
                    status=503,
                    error_type='config',
                    internal_message='STAGING_USER/STAGING_PASSWORD not configured',
                    request_origin=request_origin
                )
                self._send_response(response)
                return
            
            # In development without credentials, allow test user
            if is_development() and (not expected_user or not expected_password):
                expected_user = 'admin'
                expected_password = 'admin'
            
            # Verify credentials (constant-time comparison to prevent timing attacks)
            username_match = hmac.compare_digest(username.encode(), expected_user.encode())
            password_match = hmac.compare_digest(password.encode(), expected_password.encode())
            if not (username_match and password_match):
                # Record failed attempt for rate limiting
                record_login_attempt(client_ip)
                logger.warning(f"Failed login attempt for user: {username} from IP: {client_ip}")
                response = error_response(
                    message='Invalid username or password',
                    status=401,
                    error_type='authentication',
                    request_origin=request_origin
                )
                self._send_response(response)
                return
            
            # Generate JWT token
            try:
                token, expires_at = generate_jwt_token(username)
            except RuntimeError as e:
                logger.error(f"JWT generation failed: {e}")
                response = error_response(
                    message='Authentication service error',
                    status=500,
                    error_type='internal',
                    internal_message=str(e),
                    request_origin=request_origin
                )
                self._send_response(response)
                return
            
            # Success response
            logger.info(f"Successful login for user: {username}")
            response = json_response({
                'success': True,
                'token': token,
                'expires_at': expires_at.isoformat(),
                'user': username
            }, request_origin=request_origin)
            
        except json.JSONDecodeError:
            response = error_response(
                message='Invalid JSON in request body',
                status=400,
                error_type='validation',
                request_origin=request_origin
            )
        except Exception as e:
            logger.error(f"Unhandled login exception: {e}", exc_info=True)
            response = error_response(
                message='Authentication failed',
                status=500,
                error_type='internal',
                internal_message=str(e),
                request_origin=request_origin
            )
        
        self._send_response(response)
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        request_origin = self.headers.get('Origin', '')
        self._send_response(options_response(request_origin))
    
    def _send_response(self, response):
        """Helper to send response."""
        self.send_response(response['statusCode'])
        for key, value in response.get('headers', {}).items():
            self.send_header(key, value)
        self.end_headers()
        body = response.get('body', '')
        if body:
            self.wfile.write(body.encode() if isinstance(body, str) else body)
