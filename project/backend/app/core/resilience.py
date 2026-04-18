import asyncio
import random
import functools
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

def with_llm_resilience(fallback_default: Any = None, max_retries: int = 3, base_delay: float = 1.0, chaos_mode: bool = False):
    """
    Chaos Engineering inspired resilience decorator for LLM calls.
    
    Features:
    1. Exponential Backoff with Jitter: Prevents thundering herds on rate limits (429) or server errors (500).
    2. Chaos Injection: Randomly simulates failures if chaos_mode is True to test fallback robustness.
    3. Graceful Fallback: Returns fallback_default or executes fallback_default() if all retries are exhausted.
       If fallback_default is an Exception, it safely raises it up the call stack.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            while retries <= max_retries:
                try:
                    # Chaos Engineering: Inject artificial failures (default off)
                    if chaos_mode and random.random() < 0.1:
                        raise RuntimeError("Chaos Monkey: Simulated LLM API Failure")
                    
                    return await func(*args, **kwargs)
                    
                except Exception as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"[Resilience] {func.__name__} failed after {max_retries} retries. Error: {e}. Executing fallback.")
                        
                        # 1. Fallback is an Exception to be raised
                        if isinstance(fallback_default, Exception):
                            raise fallback_default
                        elif isinstance(fallback_default, type) and issubclass(fallback_default, Exception):
                            raise fallback_default(f"LLM call failed: {e}")
                        
                        # 2. Fallback is a dynamic callable structure
                        elif callable(fallback_default):
                            try:
                                return fallback_default(*args, **kwargs)
                            except TypeError:
                                return fallback_default()
                        
                        # 3. Fallback is a static value
                        return fallback_default
                        
                    # Exponential backoff with Full Jitter
                    sleep_time = random.uniform(0, base_delay * (2 ** (retries - 1)))
                    logger.warning(f"[Resilience] {func.__name__} error: {e}. Retrying in {sleep_time:.2f}s (Attempt {retries}/{max_retries})")
                    await asyncio.sleep(sleep_time)
        return wrapper
    return decorator