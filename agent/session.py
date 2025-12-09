"""
Tool Session management for efficient connection handling.

Implements a session-scoped connection pool that shares DB/Redis connections
across all tool calls within a single agent execution session.
"""

import logging
import os
from typing import Optional, Tuple, Any
import yaml

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ga4_extraction.database import GA4Database
from ga4_extraction.redis_cache import GA4RedisCache
from ga4_extraction.factory import GA4ResourceFactory

logger = logging.getLogger(__name__)


class ToolSession:
    """
    Context manager for managing database and cache connections across tool calls.
    
    When active, all tools share the same connections instead of creating new ones.
    Provides automatic cleanup when the session ends.
    
    Usage:
        with ToolSession(config) as session:
            result = agent.run(prompt)
        # Connections automatically closed
    
    Backward Compatibility:
        If no session is active, tools fall back to creating per-call connections.
    """
    
    _current: Optional["ToolSession"] = None
    
    def __init__(self, config: dict = None):
        """
        Initialize a tool session.
        
        Args:
            config: Configuration dict (from config.yaml). If None, loads automatically.
        """
        self.db: Optional[GA4Database] = None
        self.cache: Optional[GA4RedisCache] = None
        self.config = config
        self._owns_connections = True
    
    def __enter__(self) -> "ToolSession":
        """
        Enter the session context: load config and create connections.
        """
        # Load config if not provided
        if self.config is None:
            self.config = self._load_config()
        
        # Create connections using factory
        self.db, self.cache = GA4ResourceFactory.create_from_config(self.config)
        
        # Set as current session
        ToolSession._current = self
        
        logger.info("ToolSession started: connections opened")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit the session context: close connections and clear current session.
        """
        # Clear current session first
        ToolSession._current = None
        
        # Close connections
        if self._owns_connections:
            if self.db:
                self.db.close()
                logger.debug("Database connection closed")
            if self.cache:
                self.cache.close()
                logger.debug("Redis cache connection closed")
        
        logger.info("ToolSession ended: connections closed")
    
    @classmethod
    def get_current(cls) -> Optional["ToolSession"]:
        """
        Get the currently active session, if any.
        
        Returns:
            The active ToolSession or None if no session is active.
        """
        return cls._current
    
    @classmethod
    def is_active(cls) -> bool:
        """
        Check if a session is currently active.
        
        Returns:
            True if a session is active, False otherwise.
        """
        return cls._current is not None
    
    @staticmethod
    def _load_config() -> dict:
        """
        Load configuration from config.yaml.
        
        Returns:
            Configuration dictionary.
        """
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)


def get_connections() -> Tuple[GA4Database, Optional[GA4RedisCache], bool]:
    """
    Get database and cache connections.
    
    If a ToolSession is active, returns the session's shared connections.
    Otherwise, creates new connections (backward compatibility fallback).
    
    Returns:
        Tuple of (database, cache, should_close):
        - database: GA4Database instance
        - cache: GA4RedisCache instance or None
        - should_close: True if caller must close connections, False if managed by session
    
    Usage:
        db, cache, should_close = get_connections()
        try:
            # Use db and cache
            ...
        finally:
            if should_close:
                db.close()
                if cache:
                    cache.close()
    """
    session = ToolSession.get_current()
    
    if session:
        # Session is active: use shared connections
        return session.db, session.cache, False
    else:
        # No session: create new connections (legacy behavior)
        db, cache = _create_connections_legacy()
        return db, cache, True


def _create_connections_legacy() -> Tuple[GA4Database, Optional[GA4RedisCache]]:
    """
    Create connections using legacy method (for backward compatibility).
    
    This is called when no ToolSession is active.
    """
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    db_config = config.get('database', {})
    
    # SQLite
    db_path = db_config.get('sqlite', {}).get('path', 'data/ga4_data.db')
    db = GA4Database(db_path)
    
    # Redis (optional)
    try:
        redis_config = db_config.get('redis', {})
        cache = GA4RedisCache(
            host=redis_config.get('host', 'localhost'),
            port=redis_config.get('port', 6379),
            db=redis_config.get('db', 1),
            key_prefix=redis_config.get('key_prefix', 'ga4:metrics:'),
            ttl_days=redis_config.get('ttl_days', 21)
        )
    except Exception as e:
        logger.warning(f"Redis non disponibile: {e}")
        cache = None
    
    return db, cache

