from __future__ import annotations

import functools
import threading
import time


def ttl_cache(ttl: float = 20.0):
    """Process-wide TTL cache for pure aggregate functions.

    Sessions (SQLAlchemy Session objects) are excluded from the cache key so
    callers can pass any session. Results are deep-copied on read to keep the
    store immutable from callers.
    """

    def _is_db(arg) -> bool:
        return arg.__class__.__name__ == "Session"

    lock = threading.Lock()
    store: dict = {}

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key_parts = []
            for a in args:
                if _is_db(a):
                    key_parts.append("__db__")
                else:
                    key_parts.append(repr(a))
            for k in sorted(kwargs):
                v = kwargs[k]
                key_parts.append(f"{k}=" + ("__db__" if _is_db(v) else repr(v)))
            key = (fn.__name__, tuple(key_parts))

            now = time.monotonic()
            with lock:
                hit = store.get(key)
                if hit and (now - hit[0]) < ttl:
                    import copy

                    return copy.deepcopy(hit[1])

            result = fn(*args, **kwargs)

            with lock:
                store[key] = (now, result)
            return result

        return wrapper

    return deco