"""
Sessions Range Endpoint - GET /api/sessions/range

Recupera sessioni (totali e per canale) per un range di date.
Richiede JWT Auth.
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
    check_jwt_auth, get_db
)


# Canali di interesse
TARGET_CHANNELS = ['Paid Media e Display', 'Organic Search', 'Direct', 'Paid Search']


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler per sessioni range."""
    
    def do_GET(self):
        """GET /api/sessions/range - Sessioni per range date."""
        # Check JWT auth
        jwt_error = check_jwt_auth(self)
        if jwt_error:
            self._send_response(jwt_error)
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
            
            days_diff = (end_date - start_date).days
            if days_diff > 360:
                response = error_response(
                    'Maximum range is 360 days',
                    400,
                    'validation'
                )
                self._send_response(response)
                return
            
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
                
                # Query per PostgreSQL e SQLite
                if db.db_type == 'postgresql':
                    cursor.execute("""
                        SELECT date, channel, commodity_sessions, lucegas_sessions
                        FROM sessions_by_channel
                        WHERE date BETWEEN %s AND %s
                        AND channel IN (%s, %s, %s, %s)
                        ORDER BY date ASC, channel
                    """, (start_date_str, end_date_str, *TARGET_CHANNELS))
                else:
                    cursor.execute("""
                        SELECT date, channel, commodity_sessions, lucegas_sessions
                        FROM sessions_by_channel
                        WHERE date BETWEEN ? AND ?
                        AND channel IN (?, ?, ?, ?)
                        ORDER BY date ASC, channel
                    """, (start_date_str, end_date_str, *TARGET_CHANNELS))
                
                for row in cursor.fetchall():
                    row_dict = dict(row) if hasattr(row, 'keys') else {
                        'date': row[0],
                        'channel': row[1],
                        'commodity_sessions': row[2],
                        'lucegas_sessions': row[3]
                    }
                    by_channel.append({
                        'date': str(row_dict['date']),
                        'channel': row_dict['channel'],
                        'commodity': row_dict['commodity_sessions'],
                        'lucegas': row_dict['lucegas_sessions']
                    })
                
                response = json_response({
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

