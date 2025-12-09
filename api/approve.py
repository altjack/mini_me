"""
Approve Endpoint - POST /api/approve

Approva draft corrente (archivia + aggiorna history).
Richiede Basic Auth + API Key.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from http.server import BaseHTTPRequestHandler
from _utils import (
    json_response, error_response, options_response,
    check_basic_auth, check_api_key, get_config
)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler per approvazione draft."""
    
    def do_POST(self):
        """POST /api/approve - Approva draft corrente."""
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
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            from workflows.service import DailyReportWorkflow
            from workflows.config import ConfigLoader
            from workflows.logging import LoggerFactory
            
            config = ConfigLoader.load()
            logger = LoggerFactory.get_logger('api', config)
            
            with DailyReportWorkflow(config, logger=logger) as workflow:
                approval = workflow.run_approval(interactive=False)
                
                if approval.success:
                    response = json_response({
                        'success': True,
                        'archive_path': approval.archive_path
                    })
                else:
                    status_code = 404 if 'non trovato' in approval.message.lower() else 400
                    response = error_response(
                        approval.error or approval.message,
                        status_code,
                        'approval'
                    )
        
        except Exception as e:
            response = error_response(f'Approval error: {str(e)}', 500, 'internal')
        
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

