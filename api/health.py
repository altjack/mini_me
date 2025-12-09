"""
Health Check Endpoint - GET /api/health

Verifica che il servizio sia attivo.
Non richiede autenticazione.
"""

from datetime import datetime
from http.server import BaseHTTPRequestHandler
from _utils import json_response, with_cors


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler per health check."""
    
    def do_GET(self):
        """GET /api/health - Health check."""
        response = json_response({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'service': 'daily-report-api',
            'platform': 'vercel'
        })
        
        self.send_response(response['statusCode'])
        for key, value in response['headers'].items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response['body'].encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        from _utils import options_response
        response = options_response()
        
        self.send_response(response['statusCode'])
        for key, value in response['headers'].items():
            self.send_header(key, value)
        self.end_headers()

