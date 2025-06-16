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
import json
import pathlib
import glob # For finding all .json files in a directory

# --- Load Tool Definitions to get API paths/methods ---
TOOLS_MAP = {}
# Path to the directory containing individual tool JSON files.
# This assumes subscan_client.py is in polkaquery/data_sources/
# and polkaquery_tool_definitions/ is in the project root.
TOOLS_DIR_PATH_CLIENT = pathlib.Path(__file__).resolve().parent.parent.parent / "polkaquery_tool_definitions" / "subscan"

if TOOLS_DIR_PATH_CLIENT.is_dir():
    for tool_file_path in glob.glob(str(TOOLS_DIR_PATH_CLIENT / "*.json")):
        try:
            with open(tool_file_path, 'r') as f:
                tool_definition = json.load(f)
                tool_name = tool_definition.get("name")
                if tool_name:
                    TOOLS_MAP[tool_name] = tool_definition
                else:
                    print(f"Warning: Tool definition in {tool_file_path} is missing a 'name'.")
        except json.JSONDecodeError:
            print(f"Warning: Error decoding JSON from tool file for client: {tool_file_path}")
        except Exception as e:
            print(f"Warning: Error loading tool file for client {tool_file_path}: {e}")
    print(f"Subscan client loaded {len(TOOLS_MAP)} tools into TOOLS_MAP from: {TOOLS_DIR_PATH_CLIENT}")
else:
    print(f"Warning: Tools directory not found for Subscan client at {TOOLS_DIR_PATH_CLIENT}. API calls via tool name will fail.")
# --- End Load Tool Definitions ---


async def call_subscan_api(client: httpx.AsyncClient, base_url: str, intent_tool_name: str, params: dict, api_key: str | None) -> dict:
    """
    Calls the appropriate Subscan API endpoint based on the intent_tool_name,
    using API path and method from loaded tool definitions.
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    else:
        print("Warning: Subscan API key not provided for call_subscan_api (tool mode).")

    tool_definition = TOOLS_MAP.get(intent_tool_name)
    if not tool_definition:
        raise HTTPException(status_code=400, detail=f"Unknown intent/tool name '{intent_tool_name}' provided to Subscan client. Available: {list(TOOLS_MAP.keys())}")

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

