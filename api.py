"""
Flask API server for Daily Report workflow.

Provides REST endpoints for:
- Statistics retrieval
- Email generation
- Draft management
- Approval workflow
- Data backfill

Uses app factory pattern for testability.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import Optional
from functools import wraps

from flask import Flask, jsonify, request, Response
from flask_cors import CORS

from workflows.service import DailyReportWorkflow
from workflows.config import ConfigLoader, ConfigurationError
from workflows.logging import LoggerFactory
from workflows.result_types import StepStatus
from ga4_extraction.database import GA4Database


# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================

# Origini CORS permesse (whitelist)
ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:5174',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:5174',
    # Aggiungere domini produzione quando necessario
]


# =============================================================================
# APP FACTORY
# =============================================================================

def create_app(config: Optional[dict] = None) -> Flask:
    """
    Application factory per Flask app.
    
    Permette di creare istanze separate per testing.
    
    Args:
        config: Configurazione opzionale (caricata automaticamente se None)
        
    Returns:
        Flask app configurata
    """
    app = Flask(__name__)
    
    # CORS con whitelist origini (SECURITY FIX)
    CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)
    
    # Carica configurazione
    if config is None:
        try:
            config = ConfigLoader.load()
        except ConfigurationError as e:
            print(f"❌ Errore configurazione: {e}")
            sys.exit(1)
    
    # Salva config nell'app context
    app.config['APP_CONFIG'] = config
    
    # Setup logger
    logger = LoggerFactory.get_logger('api', config)
    app.config['LOGGER'] = logger
    
    # Registra routes
    register_routes(app)
    
    return app


# =============================================================================
# HELPERS
# =============================================================================

def get_config():
    """Recupera config da Flask app context"""
    from flask import current_app
    return current_app.config['APP_CONFIG']


def get_logger():
    """Recupera logger da Flask app context"""
    from flask import current_app
    return current_app.config['LOGGER']


def get_db():
    """
    Factory per connessione database.
    
    Crea nuova connessione per ogni request (thread-safe).
    Per produzione considerare connection pooling.
    """
    config = get_config()
    db_path = ConfigLoader.get_database_path(config)
    return GA4Database(db_path)


def require_api_key(f):
    """
    Decorator per autenticazione API Key.
    
    Richiede header 'X-API-Key' con valore corrispondente 
    alla variabile ambiente API_SECRET_KEY.
    
    Se API_SECRET_KEY non è configurata, l'autenticazione è disabilitata
    (modalità sviluppo).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected_key = os.getenv('API_SECRET_KEY')
        
        # Se API_SECRET_KEY non configurata, permetti (dev mode)
        if not expected_key:
            return f(*args, **kwargs)
        
        # Verifica API key
        if not api_key or api_key != expected_key:
            return jsonify({
                'success': False,
                'error': 'Unauthorized - Invalid or missing API key',
                'error_type': 'authentication'
            }), 401
        
        return f(*args, **kwargs)
    return decorated


def handle_errors(f):
    """
    Decorator per gestione errori consistente.
    
    Cattura eccezioni e ritorna JSON error response.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ConfigurationError as e:
            get_logger().error(f"Configuration error: {e}")
            return jsonify({
                'success': False,
                'error': 'Configuration error',  # Non esporre dettagli
                'error_type': 'configuration'
            }), 500
        except Exception as e:
            get_logger().error(f"Unexpected error in {f.__name__}: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': 'Internal server error',  # Non esporre dettagli
                'error_type': 'internal'
            }), 500
    return decorated


# =============================================================================
# ROUTES
# =============================================================================

def register_routes(app: Flask):
    """Registra tutti gli endpoint"""
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """
        Health check endpoint.
        
        Returns:
            200 se servizio OK
        """
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat()
        })
    
    @app.route('/api/stats', methods=['GET'])
    @handle_errors
    def get_stats():
        """
        Statistiche database GA4.
        
        Returns:
            JSON con statistiche aggregate
        """
        db = get_db()
        try:
            stats = db.get_statistics()
            latest_date = db.get_latest_date()
            
            # Backward compatible response for frontend
            return jsonify({
                'record_count': stats.get('record_count', 0),
                'min_date': stats.get('min_date'),
                'max_date': stats.get('max_date'),
                'avg_conversioni': round(stats.get('avg_swi_conversioni', 0), 2),
                'latest_available_date': latest_date
            })
        finally:
            db.close()
    
    @app.route('/api/generate', methods=['POST'])
    @handle_errors
    @require_api_key
    def generate_email():
        """
        Genera draft email (estrazione GA4 + AI Agent).
        
        Request Body (optional):
            {
                "date": "YYYY-MM-DD",    // Data target (default: ieri)
                "force": false           // Forza ri-estrazione
            }
        
        Returns:
            JSON con contenuto draft e metadata
        """
        logger = get_logger()
        config = get_config()
        
        # Parse request body
        data = request.get_json(silent=True) or {}
        target_date = data.get('date')
        force = data.get('force', False)
        
        logger.info(f"Generate request: date={target_date}, force={force}")
        
        # Esegui workflow
        with DailyReportWorkflow(config, logger=logger) as workflow:
            
            # Step 1: Estrazione
            extraction = workflow.run_extraction(
                target_date=target_date,
                force=force
            )
            
            if not extraction.success:
                logger.error(f"Extraction failed: {extraction.error}")
                return jsonify({
                    'success': False,
                    'error': extraction.error or extraction.message,
                    'step': 'extraction'
                }), 500
            
            # Step 2: Generazione
            generation = workflow.run_generation(skip_data_check=True)
            
            if not generation.success:
                logger.error(f"Generation failed: {generation.error}")
                return jsonify({
                    'success': False,
                    'error': generation.error or generation.message,
                    'step': 'generation'
                }), 500
            
            # Leggi contenuto draft
            with open(generation.draft_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Backward compatible response for frontend
            return jsonify({
                'success': True,
                'content': content,
                'data_date': extraction.date
            })
    
    @app.route('/api/draft', methods=['GET'])
    @handle_errors
    def get_draft():
        """
        Legge draft email corrente.
        
        Returns:
            JSON con contenuto draft o exists=false se non presente
        """
        config = get_config()
        draft_path = ConfigLoader.get_draft_path(config)
        
        if not os.path.exists(draft_path):
            return jsonify({'exists': False})
        
        with open(draft_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Backward compatible response for frontend
        return jsonify({
            'exists': True,
            'content': content
        })
    
    @app.route('/api/approve', methods=['POST'])
    @handle_errors
    @require_api_key
    def approve_draft():
        """
        Approva draft corrente (archivia + aggiorna history).
        
        Returns:
            JSON con path archivio
        """
        logger = get_logger()
        config = get_config()
        
        logger.info("Approve request received")
        
        with DailyReportWorkflow(config, logger=logger) as workflow:
            approval = workflow.run_approval(interactive=False)
            
            if approval.success:
                # Backward compatible response for frontend
                return jsonify({
                    'success': True,
                    'archive_path': approval.archive_path
                })
            else:
                status_code = 404 if 'non trovato' in approval.message.lower() else 400
                return jsonify({
                    'success': False,
                    'message': approval.error or approval.message
                }), status_code
    
    @app.route('/api/reject', methods=['POST'])
    @handle_errors
    @require_api_key
    def reject_draft():
        """
        Rifiuta e elimina draft corrente.
        
        Returns:
            JSON con conferma eliminazione
        """
        logger = get_logger()
        config = get_config()
        draft_path = ConfigLoader.get_draft_path(config)
        
        if not os.path.exists(draft_path):
            return jsonify({
                'success': False,
                'error': 'No draft found'
            }), 404
        
        os.remove(draft_path)
        logger.info(f"Draft rejected and deleted: {draft_path}")
        
        return jsonify({
            'success': True,
            'message': 'Draft deleted successfully'
        })
    
    @app.route('/api/backfill', methods=['POST'])
    @handle_errors
    @require_api_key
    def backfill():
        """
        Recupera dati GA4 per range di date.
        
        Request Body:
            {
                "start_date": "YYYY-MM-DD",  // Required
                "end_date": "YYYY-MM-DD",    // Required
                "include_channels": false    // Optional
            }
        
        Returns:
            JSON con risultati per ogni data
        """
        logger = get_logger()
        config = get_config()
        
        data = request.get_json()
        
        # Validazione input
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400
        
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        include_channels = data.get('include_channels', False)
        
        if not start_date_str or not end_date_str:
            return jsonify({
                'success': False,
                'error': 'start_date and end_date are required'
            }), 400
        
        # Parse e valida date
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }), 400
        
        if start_date > end_date:
            return jsonify({
                'success': False,
                'error': 'start_date must be before or equal to end_date'
            }), 400
        
        # Limite ragionevole
        days_diff = (end_date - start_date).days
        if days_diff > 90:
            return jsonify({
                'success': False,
                'error': 'Maximum range is 90 days'
            }), 400
        
        logger.info(f"Backfill request: {start_date_str} to {end_date_str}")
        
        # Import backfill function
        from scripts.backfill_missing_dates import backfill_single_date
        
        # Setup risorse
        db = get_db()
        redis_cache = None
        
        try:
            # Tenta connessione Redis (opzionale)
            redis_config = ConfigLoader.get_redis_config(config)
            if redis_config:
                from ga4_extraction.redis_cache import GA4RedisCache
                try:
                    redis_cache = GA4RedisCache(
                        host=redis_config.get('host', 'localhost'),
                        port=redis_config.get('port', 6379),
                        db=redis_config.get('db', 1)
                    )
                except Exception as e:
                    logger.warning(f"Redis not available: {e}")
            
            # Esegui backfill per ogni data
            results = []
            current_date = start_date
            
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                
                try:
                    success = backfill_single_date(
                        date_str, 
                        db, 
                        redis_cache,
                        include_channels=include_channels
                    )
                    results.append({
                        'date': date_str,
                        'success': success,
                        'error': None
                    })
                except Exception as e:
                    logger.error(f"Backfill error for {date_str}: {e}")
                    results.append({
                        'date': date_str,
                        'success': False,
                        'error': str(e)
                    })
                
                current_date += timedelta(days=1)
            
            # Calcola statistiche
            success_count = sum(1 for r in results if r['success'])
            
            return jsonify({
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
            if redis_cache:
                redis_cache.close()
    
    @app.route('/api/workflow/full', methods=['POST'])
    @handle_errors
    @require_api_key
    def run_full_workflow():
        """
        Esegue workflow completo: Extract → Generate → Approve
        
        Request Body (optional):
            {
                "date": "YYYY-MM-DD",
                "force": false,
                "auto_approve": true  // Required for non-interactive
            }
        
        Returns:
            JSON con risultati di tutti gli step
        """
        logger = get_logger()
        config = get_config()
        
        data = request.get_json(silent=True) or {}
        target_date = data.get('date')
        force = data.get('force', False)
        auto_approve = data.get('auto_approve', True)
        
        logger.info(f"Full workflow request: date={target_date}, force={force}, auto_approve={auto_approve}")
        
        with DailyReportWorkflow(config, logger=logger) as workflow:
            result = workflow.run_full(
                target_date=target_date,
                force_extraction=force,
                auto_approve=auto_approve
            )
            
            # Costruisci risposta
            steps_data = []
            for step in result.steps:
                step_data = {
                    'status': step.status.name,
                    'message': step.message,
                    'success': step.success
                }
                if step.error:
                    step_data['error'] = step.error
                
                # Aggiungi attributi specifici per tipo
                if hasattr(step, 'date') and step.date:
                    step_data['date'] = step.date
                if hasattr(step, 'draft_path') and step.draft_path:
                    step_data['draft_path'] = step.draft_path
                if hasattr(step, 'archive_path') and step.archive_path:
                    step_data['archive_path'] = step.archive_path
                
                steps_data.append(step_data)
            
            return jsonify({
                'success': result.success,
                'data': {
                    'steps': steps_data,
                    'duration_seconds': round(result.duration_seconds, 2),
                    'errors': result.errors
                }
            })
    
    @app.route('/api/metrics/range', methods=['GET'])
    @handle_errors
    def get_metrics_range():
        """
        Recupera metriche per un range di date (per dashboard).
        
        Query Parameters:
            start_date: Data inizio (YYYY-MM-DD), default: 45 giorni fa
            end_date: Data fine (YYYY-MM-DD), default: ieri
        
        Returns:
            JSON con lista di metriche giornaliere incluso flag weekend
        """
        # Parse parametri con default a ultimi 45 giorni
        end_date_str = request.args.get('end_date')
        start_date_str = request.args.get('start_date')
        
        # Default: ultimi 45 giorni fino a ieri
        if not end_date_str:
            end_date = datetime.now() - timedelta(days=1)
            end_date_str = end_date.strftime('%Y-%m-%d')
        else:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        if not start_date_str:
            start_date = end_date - timedelta(days=44)  # 45 giorni totali
            start_date_str = start_date.strftime('%Y-%m-%d')
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        
        # Validazione
        if start_date > end_date:
            return jsonify({
                'success': False,
                'error': 'start_date must be before or equal to end_date'
            }), 400
        
        # Limite massimo 90 giorni
        days_diff = (end_date - start_date).days
        if days_diff > 90:
            return jsonify({
                'success': False,
                'error': 'Maximum range is 90 days'
            }), 400
        
        db = get_db()
        try:
            metrics = db.get_date_range(start_date_str, end_date_str)
            
            # Arricchisci con flag weekend e formatta per frontend
            result = []
            for m in metrics:
                date_obj = datetime.strptime(m['date'], '%Y-%m-%d')
                is_weekend = date_obj.weekday() >= 5  # Sabato=5, Domenica=6
                
                result.append({
                    'date': m['date'],
                    'swi': m['swi_conversioni'],
                    'isWeekend': is_weekend
                })
            
            # Calcola media per linea di riferimento
            swi_values = [r['swi'] for r in result if r['swi'] is not None]
            avg_swi = round(sum(swi_values) / len(swi_values), 2) if swi_values else 0
            
            return jsonify({
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
    
    @app.route('/api/sessions/range', methods=['GET'])
    @handle_errors
    def get_sessions_range():
        """
        Recupera sessioni (totali e per canale) per un range di date.
        
        Query Parameters:
            start_date: Data inizio (YYYY-MM-DD), default: 45 giorni fa
            end_date: Data fine (YYYY-MM-DD), default: ieri
        
        Returns:
            JSON con totali giornalieri e breakdown per canale
        """
        # Parse parametri (stessa logica di metrics/range)
        end_date_str = request.args.get('end_date')
        start_date_str = request.args.get('start_date')
        
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
        
        if start_date > end_date:
            return jsonify({
                'success': False,
                'error': 'start_date must be before or equal to end_date'
            }), 400
        
        days_diff = (end_date - start_date).days
        if days_diff > 90:
            return jsonify({
                'success': False,
                'error': 'Maximum range is 90 days'
            }), 400
        
        # Canali di interesse
        TARGET_CHANNELS = ['Paid Media e Display', 'Organic Search', 'Direct', 'Paid Search']
        
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
            cursor.execute("""
                SELECT date, channel, commodity_sessions, lucegas_sessions
                FROM sessions_by_channel
                WHERE date BETWEEN ? AND ?
                AND channel IN (?, ?, ?, ?)
                ORDER BY date ASC, channel
            """, (start_date_str, end_date_str, *TARGET_CHANNELS))
            
            for row in cursor.fetchall():
                by_channel.append({
                    'date': row['date'],
                    'channel': row['channel'],
                    'commodity': row['commodity_sessions'],
                    'lucegas': row['lucegas_sessions']
                })
            
            return jsonify({
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


# =============================================================================
# MAIN
# =============================================================================

# Create app instance for direct execution
app = create_app()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Daily Report API Server')
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=5001,
        help='Port to run server on (default: 5001)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )
    args = parser.parse_args()
    
    print(f"🚀 Starting API server on {args.host}:{args.port}...")
    app.run(host=args.host, port=args.port, debug=args.debug)
