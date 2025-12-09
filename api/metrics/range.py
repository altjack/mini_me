"""
Metrics Range Endpoint - GET /api/metrics/range

Recupera metriche per un range di date (per dashboard).
Richiede Basic Auth.
"""

import os
import sys
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Aggiungi parent dir per import _utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _utils import (
    json_response, error_response, options_response,
    check_basic_auth, get_db
)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler per metriche range."""
    
    def do_GET(self):
        """GET /api/metrics/range - Metriche per range date."""
        # Check auth
        auth_error = check_basic_auth(self)
        if auth_error:
            self._send_response(auth_error)
            return
        
        try:
            # Parse query params
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            
            end_date_str = params.get('end_date', [None])[0]
            start_date_str = params.get('start_date', [None])[0]
            
            # Default: ultimi 45 giorni fino a ieri
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
            
            # Validazione
            if start_date > end_date:
                response = error_response(
                    'start_date must be before or equal to end_date',
                    400,
                    'validation'
                )
                self._send_response(response)
                return
            
            # Limite massimo 90 giorni
            days_diff = (end_date - start_date).days
            if days_diff > 90:
                response = error_response(
                    'Maximum range is 90 days',
                    400,
                    'validation'
                )
                self._send_response(response)
                return
            
            db = get_db()
            try:
                metrics = db.get_date_range(start_date_str, end_date_str)
                
                # Arricchisci con flag weekend
                result = []
                for m in metrics:
                    date_obj = datetime.strptime(m['date'], '%Y-%m-%d')
                    is_weekend = date_obj.weekday() >= 5
                    
                    result.append({
                        'date': m['date'],
                        'swi': m['swi_conversioni'],
                        'isWeekend': is_weekend
                    })
                
                # Calcola media
                swi_values = [r['swi'] for r in result if r['swi'] is not None]
                avg_swi = round(sum(swi_values) / len(swi_values), 2) if swi_values else 0
                
                response = json_response({
                    'success': True,
                    'data': result,
                    'meta': {
                        'start_date': start_date_str,
                        'end_date': end_date_str,
                        'count': len(result),
                        'average': avg_swi
                    }
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

