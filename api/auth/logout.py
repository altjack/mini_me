"""
Logout Endpoint - POST /api/auth/logout

Clears authentication state.
For JWT-based auth, the client is responsible for clearing the stored token.
This endpoint simply confirms the logout and clears any server-side cookie.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler
from _utils import json_response, options_response, get_cors_headers


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for logout."""
    
    def do_POST(self):
        """POST /api/auth/logout - Clear authentication."""
        request_origin = self.headers.get('Origin', '')
        
        # Create success response
        response_data = {
            'success': True,
            'message': 'Logged out successfully'
        }
        
        # Build response with cookie clearing
        headers = get_cors_headers(request_origin)
        headers['Content-Type'] = 'application/json'
        
        # Clear auth cookie if it exists (for same-domain setups)
        # Set cookie with expired date to clear it
        headers['Set-Cookie'] = 'auth_token=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax'
        
        self._send_json_response(response_data, headers)
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self._send_response(options_response(self.headers.get('Origin', '')))
    
    def _send_json_response(self, data, headers, status=200):
        """Helper to send JSON response with custom headers."""
        import json
        body = json.dumps(data)
        
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body.encode())
    
    def _send_response(self, response):
        """Helper to send response."""
        self.send_response(response['statusCode'])
        for key, value in response.get('headers', {}).items():
            self.send_header(key, value)
        self.end_headers()
        body = response.get('body', '')
        if body:
            self.wfile.write(body.encode() if isinstance(body, str) else body)
