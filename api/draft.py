"""
Draft Endpoint - GET /api/draft

Legge il draft email corrente.
Richiede Basic Auth.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import BaseHTTPRequestHandler
from _utils import (
    json_response, options_response,
    check_basic_auth, get_draft_path
)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler per lettura draft."""
    
    def do_GET(self):
        """GET /api/draft - Legge draft corrente."""
        # Check auth
        auth_error = check_basic_auth(self)
        if auth_error:
            self._send_response(auth_error)
            return
        
        draft_path = get_draft_path()
        
        if not os.path.exists(draft_path):
            response = json_response({'exists': False})
        else:
            try:
                with open(draft_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                response = json_response({
                    'exists': True,
                    'content': content
                })
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Draft read error: {e}")
                response = json_response({
                    'exists': False,
                    'error': 'Unable to read draft file'
                })
        
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

