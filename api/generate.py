"""
Generate Endpoint - POST /api/generate

Genera draft email (estrazione GA4 + AI Agent).
Richiede JWT Auth.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from http.server import BaseHTTPRequestHandler
from _utils import (
    json_response, error_response, options_response,
    check_jwt_auth, get_json_body,
    get_config, get_draft_path
)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler per generazione email."""
    
    def do_POST(self):
        """POST /api/generate - Genera draft email."""
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
            
            target_date = data.get('date')
            force = data.get('force', False)
            
            # Import workflow
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            from backend.workflows.service import DailyReportWorkflow
            from backend.workflows.config import ConfigLoader
            from backend.workflows.logging import LoggerFactory
            
            # Carica config
            config = ConfigLoader.load()
            logger = LoggerFactory.get_logger('api', config)
            
            # Crea directory temporanea per draft
            draft_dir = os.path.dirname(get_draft_path())
            os.makedirs(draft_dir, exist_ok=True)
            
            # Esegui workflow
            with DailyReportWorkflow(config, logger=logger) as workflow:
                # Step 1: Estrazione
                extraction = workflow.run_extraction(
                    target_date=target_date,
                    force=force
                )
                
                if not extraction.success:
                    response = error_response(
                        extraction.error or extraction.message,
                        500,
                        'extraction'
                    )
                    self._send_response(response)
                    return
                
                # Step 2: Generazione
                generation = workflow.run_generation(skip_data_check=True)
                
                if not generation.success:
                    response = error_response(
                        generation.error or generation.message,
                        500,
                        'generation'
                    )
                    self._send_response(response)
                    return
                
                # Leggi contenuto draft
                with open(generation.draft_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                response = json_response({
                    'success': True,
                    'content': content,
                    'data_date': extraction.date
                })
        
        except Exception as e:
            from _utils import safe_error_response
            response = safe_error_response(
                error_type='generation',
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

