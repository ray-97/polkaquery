# Polkaquery
# Copyright (C) 2025 Ray
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import json
from functools import wraps
from cachetools import TTLCache, keys

# Define shared cache objects
api_cache = TTLCache(maxsize=1024, ttl=300)
llm_cache = TTLCache(maxsize=256, ttl=3600)

def async_cached(cache, key=keys.hashkey):
    """
    An async-aware caching decorator that correctly handles caching the
    results of coroutines.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            k = key(*args, **kwargs)
            try:
                return cache[k]
            except KeyError:
                pass  # key not found
            
            # Await the coroutine to get the result
            result = await func(*args, **kwargs)
            
            # Store the result in the cache
            cache[k] = result
            return result
        return wrapper
    return decorator

# --- Custom Key Generators ---

def api_call_caching_key(*args, **kwargs):
    """
    Creates a stable cache key for API calls based on the tool definition and parameters.
    """
    tool_def = kwargs.get("tool_definition", {})
    params = kwargs.get("params", {})
    tool_name = tool_def.get("name", "unknown_tool")
    sorted_params = json.dumps(params, sort_keys=True)
    return keys.hashkey(f"{tool_name}:{sorted_params}")

def llm_recognizer_caching_key(*args, **kwargs):
    """
    Creates a stable cache key for the tool recognizer LLM call.
    """
    query = kwargs.get('query', args[0] if args else None)
    prompt_template = kwargs.get('prompt_template', args[3] if len(args) > 3 else None)
    return keys.hashkey((query, prompt_template))
