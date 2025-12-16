"""
Backfill Endpoint - POST /api/backfill

Recupera dati GA4 per range di date.
Richiede JWT Auth.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from _utils import (
    json_response, error_response, options_response,
    check_jwt_auth, get_db,
    validate_date_string, safe_error_response,
    is_production
)
import logging
logger = logging.getLogger(__name__)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler per backfill dati."""
    
    def do_POST(self):
        """POST /api/backfill - Backfill dati GA4."""
        # Check JWT auth
        jwt_error = check_jwt_auth(self)
        if jwt_error:
            self._send_response(jwt_error)
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
            dry_run = data.get('dry_run', False)
            
            # Validazione date con funzione sicura
            start_error = validate_date_string(start_date_str, 'start_date')
            if start_error:
                response = error_response(start_error, 400, 'validation')
                self._send_response(response)
                return
            
            end_error = validate_date_string(end_date_str, 'end_date')
            if end_error:
                response = error_response(end_error, 400, 'validation')
                self._send_response(response)
                return
            
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            
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
            
            # Calcola data massima per canali (D-2) - GA4 richiede ~48h di ritardo
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            max_channel_date = today - timedelta(days=2)
            
            # Import backfill function
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from scripts.backfill_missing_dates import backfill_single_date
            from ga4_extraction.extraction import extract_for_date, extract_sessions_channels_delayed
            
            db = None
            try:
                # Modalità dry_run: estrai e restituisci i dati senza scrivere su DB
                if dry_run:
                    results = []
                    current_date = start_date
                    while current_date <= end_date:
                        date_str = current_date.strftime('%Y-%m-%d')
                        try:
                            ga4_result, _dates = extract_for_date(date_str)
                            results.append({
                                'date': date_str,
                                'success': True,
                                'error': None,
                                'ga4_preview': {
                                    'sessioni': ga4_result.get('sessioni'),
                                    'sessioni_lucegas': ga4_result.get('sessioni_lucegas'),
                                    'swi': ga4_result.get('swi')
                                }
                            })
                        except Exception as e:
                            logger.error(f"Dry-run error for {date_str}: {e}", exc_info=True)
                            results.append({
                                'date': date_str,
                                'success': False,
                                'error': str(e)
                            })
                        current_date += timedelta(days=1)

                    success_count = sum(1 for r in results if r['success'])
                    response = json_response({
                        'success': True,
                        'dry_run': True,
                        'data': {
                            'total': len(results),
                            'successful': success_count,
                            'failed': len(results) - success_count,
                            'details': results
                        }
                    })
                    self._send_response(response)
                    return

                db = get_db()
                
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
                            None,  # No Redis cache in serverless
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
                        # Log errore interno
                        logger.error(f"Backfill error for {date_str}: {e}", exc_info=True)
                        # Espone l'errore (staging) per debug puntuale
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
                
                response = json_response({
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
                if db:
                    db.close()
        
        except Exception as e:
            # Use safe error response to avoid exposing internal details
            if is_production():
                response = safe_error_response(
                    error_type='internal',
                    internal_error=e,
                    user_message='Backfill operation failed. Please try again later.',
                    status=500
                )
            else:
                # In staging/dev, show more details for debugging
                logger.error(f"Unhandled backfill exception: {e}", exc_info=True)
                response = error_response(
                    message=f'Backfill failed: {e}',
                    status=500,
                    error_type='internal'
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

