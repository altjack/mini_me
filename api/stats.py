"""
Stats Endpoint - GET /api/stats

Restituisce statistiche aggregate del database GA4.
Richiede JWT Auth.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import BaseHTTPRequestHandler
from _utils import (
    json_response, error_response, options_response,
    check_jwt_auth, get_db
)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler per statistiche."""
    
    def do_GET(self):
        """GET /api/stats - Statistiche database."""
        # Check JWT auth
        jwt_error = check_jwt_auth(self)
        if jwt_error:
            self._send_response(jwt_error)
            return
        
        try:
            db = get_db()
            try:
                stats = db.get_statistics()
                latest_date = db.get_latest_date()
                
                response = json_response({
                    'record_count': stats.get('record_count', 0),
                    'min_date': stats.get('min_date'),
                    'max_date': stats.get('max_date'),
                    'avg_conversioni': round(stats.get('avg_swi_conversioni', 0) or 0, 2),
                    'latest_available_date': latest_date
                })
            finally:
                db.close()
        except Exception as e:
            from _utils import safe_error_response
            response = safe_error_response(
                error_type='database',
                internal_error=e,
                status=500
            )
        
        self._send_response(response)
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self._send_response(options_response())
    
    def _send_response(self, response):
        """Helper per inviare risposta."""
        self.send_response(response['statusCode'])
        for key, value in response.get('headers', {}).items():
            self.send_header(key, value)
        self.end_headers()
        body = response.get('body', '')
        if body:
            self.wfile.write(body.encode() if isinstance(body, str) else body)

