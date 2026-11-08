from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared limiter instance. Lives in its own module (instead of main.py) so
# route modules can import it and add per-endpoint limits without a circular
# import on app.main.
#
# default_limits is a baseline applied to every route (via SlowAPIMiddleware
# in main.py) as a safety net against flooding; endpoints that need a
# tighter limit (e.g. login) declare their own @limiter.limit(...).
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
