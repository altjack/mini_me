"""
Backfill Endpoint - POST /api/backfill

Recupera dati GA4 per range di date.
Richiede Basic Auth + API Key.
"""

import os
import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from _utils import (
    json_response, error_response, options_response,
    check_basic_auth, check_api_key, get_db
)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler per backfill dati."""
    
    def do_POST(self):
        """POST /api/backfill - Backfill dati GA4."""
        # Check auth
        auth_error = check_basic_auth(self)
        if auth_error:
            self._send_response(auth_error)
            return
        
        api_error = check_api_key(self)
        if api_error:
            self._send_response(api_error)
            return
        
        try:
            # Parse request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            data = json.loads(body.decode('utf-8')) if body else {}
            
            # Validazione input
            start_date_str = data.get('start_date')
            end_date_str = data.get('end_date')
            include_channels = data.get('include_channels', False)
            
            if not start_date_str or not end_date_str:
                response = error_response(
                    'start_date and end_date are required',
                    400,
                    'validation'
                )
                self._send_response(response)
                return
            
            # Parse e valida date
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            except ValueError:
                response = error_response(
                    'Invalid date format. Use YYYY-MM-DD',
                    400,
                    'validation'
                )
                self._send_response(response)
                return
            
            if start_date > end_date:
                response = error_response(
                    'start_date must be before or equal to end_date',
                    400,
                    'validation'
                )
                self._send_response(response)
                return
            
            # Limite ragionevole
            days_diff = (end_date - start_date).days
            if days_diff > 90:
                response = error_response(
                    'Maximum range is 90 days',
                    400,
                    'validation'
                )
                self._send_response(response)
                return
            
            # Import backfill function
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from scripts.backfill_missing_dates import backfill_single_date
            
            db = get_db()
            
            try:
                # Esegui backfill per ogni data
                results = []
                current_date = start_date
                
                while current_date <= end_date:
                    date_str = current_date.strftime('%Y-%m-%d')
                    
                    try:
                        success = backfill_single_date(
                            date_str, 
                            db, 
                            None,  # No Redis cache in serverless
                            include_channels=include_channels
                        )
                        results.append({
                            'date': date_str,
                            'success': success,
                            'error': None
                        })
                    except Exception as e:
                        results.append({
                            'date': date_str,
                            'success': False,
                            'error': str(e)
                        })
                    
                    current_date += timedelta(days=1)
                
                # Calcola statistiche
                success_count = sum(1 for r in results if r['success'])
                
                response = json_response({
                    'success': True,
                    'data': {
                        'total': len(results),
                        'successful': success_count,
                        'failed': len(results) - success_count,
                        'details': results
                    }
                })
            
            finally:
                db.close()
        
        except Exception as e:
            response = error_response(f'Backfill error: {str(e)}', 500, 'internal')
        
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

