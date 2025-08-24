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

import httpx
from fastapi import HTTPException
from polkaquery.core.async_cache import async_cached, api_cache, api_call_caching_key

@async_cached(cache=api_cache, key=api_call_caching_key)
async def call_subscan_api(
    client: httpx.AsyncClient, 
    base_url: str, 
    tool_definition: dict, 
    params: dict, 
    api_key: str | None
) -> dict:
    """
    Calls the appropriate Subscan API endpoint based on the provided tool_definition.
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    else:
        print("Warning: Subscan API key not provided for call_subscan_api.")

    intent_tool_name = tool_definition.get("name", "unnamed_tool")
    api_path = tool_definition.get("api_path")
    api_method = tool_definition.get("api_method", "POST").upper() 

    if not api_path:
        raise HTTPException(status_code=500, detail=f"API path not defined for tool '{intent_tool_name}'.")

    request_body = {}
    tool_param_schema = tool_definition.get("parameters", {}).get("properties", {})
    
    for param_name, param_details in tool_param_schema.items():
        if param_name in params:
            request_body[param_name] = params[param_name]
        elif "default" in param_details: # Use default if param not provided by LLM but defined in schema
            request_body[param_name] = param_details["default"]
        # If a required param (by schema) is missing here, it implies LLM failed to extract it,
        # but gemini_recognizer should have caught it. Or it's optional without default.

    url = f"{base_url}{api_path}"
    # print(f"DEBUG: Calling Subscan API (Tool Mode): {api_method} {url} Body: {json.dumps(request_body)}")

    try:
        if api_method == "POST":
             response = await client.post(url, headers=headers, json=request_body)
        elif api_method == "GET":
             # For GET, parameters are typically URL query params, not a JSON body
             response = await client.get(url, headers=headers, params=request_body) 
        else:
            raise HTTPException(status_code=500, detail=f"Unsupported API method '{api_method}' for tool '{intent_tool_name}'.")

        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
             error_message = data.get('message', 'Unknown Subscan API error')
             print(f"Subscan API returned error code {data.get('code')}: {error_message}")
             raise HTTPException(status_code=400, detail=f"Subscan API Error: {error_message}")

        # print(f"DEBUG: Subscan API Response Code (Tool Mode): {data.get('code')}")
        return data
    except httpx.RequestError as e:
        print(f"Network error calling {url} (Tool Mode): {e}")
        raise HTTPException(status_code=503, detail=f"Network error calling Subscan API (Tool Mode): {e}")

