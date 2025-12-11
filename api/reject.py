"""
Reject Endpoint - POST /api/reject

Rifiuta e elimina draft corrente.
Richiede JWT Auth.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from http.server import BaseHTTPRequestHandler
from _utils import (
    json_response, error_response, options_response,
    check_jwt_auth, get_draft_path
)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler per rifiuto draft."""
    
    def do_POST(self):
        """POST /api/reject - Rifiuta draft corrente."""
        # Check JWT auth
        jwt_error = check_jwt_auth(self)
        if jwt_error:
            self._send_response(jwt_error)
            return
        
        try:
            draft_path = get_draft_path()
            
            if not os.path.exists(draft_path):
                response = error_response('No draft found', 404, 'not_found')
            else:
                os.remove(draft_path)
                response = json_response({
                    'success': True,
                    'message': 'Draft deleted successfully'
                })
        
        except Exception as e:
            response = error_response(f'Reject error: {str(e)}', 500, 'internal')
        
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

