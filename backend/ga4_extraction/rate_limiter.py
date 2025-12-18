"""
Rate Limiter per GA4 API.

Implementa token bucket rate limiting per rispettare i limiti GA4:
- 10 requests per secondo (burst)
- 25,000 requests per giorno (quota)

Utilizzo:
    from backend.ga4_extraction.rate_limiter import get_rate_limiter

    limiter = get_rate_limiter()
    limiter.wait_if_needed()  # Chiama prima di ogni API request
    response = client.run_report(request)
"""

import time
import threading
import logging
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class GA4RateLimiter:
    """
    Token bucket rate limiter per GA4 API.

    Features:
    - Limita requests per secondo (default: 9, sotto il limite GA4 di 10)
    - Thread-safe per utilizzo concorrente
    - Logging quando throttling attivo
    """

    def __init__(self, max_rps: int = 9):
        """
        Inizializza rate limiter.

        Args:
            max_rps: Max requests per secondo (default: 9, sotto il limite GA4)
        """
        self.max_rps = max_rps
        self.window_seconds = 1.0
        self.request_times: deque = deque()
        self._lock = threading.Lock()

        # Stats per monitoring
        self._total_requests = 0
        self._total_wait_time = 0.0

        logger.debug(f"Rate limiter inizializzato: {max_rps} rps")

    def wait_if_needed(self) -> float:
        """
        Attende se necessario per rispettare il rate limit.

        Deve essere chiamato PRIMA di ogni API request.

        Returns:
            Tempo di attesa effettivo in secondi (0 se nessuna attesa)
        """
        with self._lock:
            now = time.time()

            # Rimuovi request più vecchie della finestra temporale
            while self.request_times and self.request_times[0] < now - self.window_seconds:
                self.request_times.popleft()

            wait_time = 0.0

            # Se siamo al limite, calcola quanto aspettare
            if len(self.request_times) >= self.max_rps:
                oldest = self.request_times[0]
                wait_time = self.window_seconds - (now - oldest)

                if wait_time > 0:
                    logger.debug(f"Rate limit raggiunto, attendo {wait_time:.3f}s")
                    time.sleep(wait_time)
                    now = time.time()

                    # Pulisci di nuovo dopo sleep
                    while self.request_times and self.request_times[0] < now - self.window_seconds:
                        self.request_times.popleft()

            # Registra questa request
            self.request_times.append(time.time())

            # Aggiorna stats
            self._total_requests += 1
            self._total_wait_time += wait_time

            return wait_time

    def get_stats(self) -> dict:
        """
        Restituisce statistiche sul rate limiting.

        Returns:
            Dict con total_requests, total_wait_time, avg_wait_time
        """
        with self._lock:
            avg_wait = self._total_wait_time / self._total_requests if self._total_requests > 0 else 0
            return {
                "total_requests": self._total_requests,
                "total_wait_time": self._total_wait_time,
                "avg_wait_time": avg_wait,
                "max_rps": self.max_rps,
            }

    def reset_stats(self):
        """Resetta le statistiche (utile per test)."""
        with self._lock:
            self._total_requests = 0
            self._total_wait_time = 0.0


# Singleton globale
_rate_limiter: Optional[GA4RateLimiter] = None


def get_rate_limiter() -> GA4RateLimiter:
    """
    Ottiene l'istanza singleton del rate limiter.

    Carica max_rps dalla configurazione centralizzata.

    Returns:
        Istanza GA4RateLimiter
    """
    global _rate_limiter
    if _rate_limiter is None:
        try:
            from backend.ga4_extraction.app_config import get_config
            config = get_config()
            max_rps = config.ga4.rate_limit_rps
        except Exception:
            # Fallback a default se config non disponibile
            max_rps = 9

        _rate_limiter = GA4RateLimiter(max_rps=max_rps)

    return _rate_limiter


def reset_rate_limiter():
    """Resetta il rate limiter singleton (utile per test)."""
    global _rate_limiter
    _rate_limiter = None


if __name__ == "__main__":
    # Test standalone
    logging.basicConfig(level=logging.DEBUG)

    limiter = GA4RateLimiter(max_rps=5)

    print("Test rate limiting (10 requests con limit 5 rps)...")
    start = time.time()

    for i in range(10):
        wait = limiter.wait_if_needed()
        print(f"  Request {i+1}: wait={wait:.3f}s")

    elapsed = time.time() - start
    print(f"\nTempo totale: {elapsed:.2f}s (atteso ~2s)")
    print(f"Stats: {limiter.get_stats()}")
