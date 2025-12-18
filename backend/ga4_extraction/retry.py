"""
Retry Logic per GA4 API.

Implementa exponential backoff con jitter per gestire errori transitori.

Utilizzo:
    from backend.ga4_extraction.retry import ga4_retry, execute_with_retry

    # Come decorator
    @ga4_retry()
    def my_ga4_call():
        return client.run_report(request)

    # Come context manager
    response = execute_with_retry(lambda: client.run_report(request))
"""

import time
import random
import logging
from functools import wraps
from typing import Callable, TypeVar, Optional, Tuple, Type

logger = logging.getLogger(__name__)

T = TypeVar("T")


# Errori GA4/Google API su cui fare retry (transitori)
RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,  # Include network errors
)

# Aggiungi eccezioni Google se disponibili
try:
    from google.api_core import exceptions as google_exceptions

    RETRYABLE_EXCEPTIONS = RETRYABLE_EXCEPTIONS + (
        google_exceptions.ServiceUnavailable,  # 503
        google_exceptions.TooManyRequests,  # 429
        google_exceptions.DeadlineExceeded,  # Timeout
        google_exceptions.InternalServerError,  # 500
        google_exceptions.ResourceExhausted,  # Quota exceeded
    )
except ImportError:
    pass

# Errori su cui NON fare retry (permanenti)
PERMANENT_EXCEPTIONS: Tuple[Type[Exception], ...] = ()

try:
    from google.api_core import exceptions as google_exceptions

    PERMANENT_EXCEPTIONS = (
        google_exceptions.PermissionDenied,  # 403
        google_exceptions.Unauthenticated,  # 401
        google_exceptions.InvalidArgument,  # 400
        google_exceptions.NotFound,  # 404
    )
except ImportError:
    pass


class RetryConfig:
    """Configurazione per retry logic."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        """
        Inizializza configurazione retry.

        Args:
            max_attempts: Numero massimo di tentativi (default: 3)
            base_delay: Delay base in secondi (default: 2.0)
            max_delay: Delay massimo in secondi (default: 60.0)
            exponential_base: Base per exponential backoff (default: 2.0)
            jitter: Se True, aggiunge random jitter al delay (default: True)
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def calculate_delay(self, attempt: int) -> float:
        """
        Calcola delay per il tentativo corrente.

        Args:
            attempt: Numero tentativo (0-indexed)

        Returns:
            Delay in secondi
        """
        # Exponential backoff: base_delay * (exponential_base ^ attempt)
        delay = self.base_delay * (self.exponential_base ** attempt)

        # Cap al max_delay
        delay = min(delay, self.max_delay)

        # Aggiungi jitter (±25%)
        if self.jitter:
            jitter_range = delay * 0.25
            delay = delay + random.uniform(-jitter_range, jitter_range)

        return max(0, delay)


def _get_default_config() -> RetryConfig:
    """Ottiene configurazione retry dai settings centralizzati."""
    try:
        from backend.ga4_extraction.app_config import get_config

        config = get_config()
        return RetryConfig(
            max_attempts=config.ga4.retry_max_attempts,
            base_delay=config.ga4.retry_base_delay,
            max_delay=config.ga4.retry_max_delay,
        )
    except Exception:
        # Fallback a default
        return RetryConfig()


def ga4_retry(
    max_attempts: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
):
    """
    Decorator per retry automatico su chiamate GA4 API.

    Applica exponential backoff con jitter su errori transitori.
    Non fa retry su errori permanenti (auth, permission, etc.).

    Args:
        max_attempts: Override numero tentativi (default: da config)
        base_delay: Override delay base (default: da config)
        max_delay: Override delay massimo (default: da config)

    Returns:
        Decorator function

    Usage:
        @ga4_retry()
        def call_ga4_api():
            return client.run_report(request)

        @ga4_retry(max_attempts=5)
        def critical_call():
            return client.run_report(important_request)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Ottieni config (con override se specificati)
            config = _get_default_config()
            if max_attempts is not None:
                config.max_attempts = max_attempts
            if base_delay is not None:
                config.base_delay = base_delay
            if max_delay is not None:
                config.max_delay = max_delay

            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)

                except PERMANENT_EXCEPTIONS as e:
                    # Errori permanenti: non fare retry
                    logger.error(f"Errore permanente (no retry): {type(e).__name__}: {e}")
                    raise

                except RETRYABLE_EXCEPTIONS as e:
                    last_exception = e
                    remaining = config.max_attempts - attempt - 1

                    if remaining > 0:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"Errore transiente (tentativo {attempt + 1}/{config.max_attempts}): "
                            f"{type(e).__name__}: {e}. "
                            f"Retry in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Errore dopo {config.max_attempts} tentativi: "
                            f"{type(e).__name__}: {e}"
                        )

                except Exception as e:
                    # Eccezioni non classificate: log e propaga
                    logger.error(f"Errore non classificato: {type(e).__name__}: {e}")
                    raise

            # Se arriviamo qui, abbiamo esaurito i tentativi
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def execute_with_retry(
    func: Callable[[], T],
    max_attempts: Optional[int] = None,
    base_delay: Optional[float] = None,
) -> T:
    """
    Esegue una funzione con retry logic.

    Alternativa al decorator per casi dove il decorator non è pratico.

    Args:
        func: Funzione da eseguire (callable senza argomenti)
        max_attempts: Override numero tentativi
        base_delay: Override delay base

    Returns:
        Risultato della funzione

    Usage:
        response = execute_with_retry(
            lambda: client.run_report(request),
            max_attempts=3
        )
    """

    @ga4_retry(max_attempts=max_attempts, base_delay=base_delay)
    def _wrapper():
        return func()

    return _wrapper()


if __name__ == "__main__":
    # Test standalone
    logging.basicConfig(level=logging.DEBUG)

    # Simula errori transitori
    call_count = 0

    @ga4_retry(max_attempts=3, base_delay=0.5)
    def flaky_function():
        global call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError(f"Simulated error (attempt {call_count})")
        return "Success!"

    print("Test retry logic...")
    try:
        result = flaky_function()
        print(f"Risultato: {result}")
        print(f"Tentativi: {call_count}")
    except Exception as e:
        print(f"Fallito dopo tutti i tentativi: {e}")
