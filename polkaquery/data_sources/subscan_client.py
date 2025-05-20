# Polkaquery
# Copyright (C) 2025 Polkaquery_Team

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# subscan_client.py
import httpx
from fastapi import HTTPException

# todo: find exact Subscan API v2 endpoints and their request/response structures for these intents

async def call_subscan_api(client: httpx.AsyncClient, base_url: str, intent: str, params: dict, api_key: str | None) -> dict:
    """
    Calls the appropriate Subscan API endpoint based on the intent.
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    else:
        print("Warning: Subscan API key not provided for call_subscan_api.")

    api_path = ""
    request_body = None
    method = "POST"

    if intent == "get_balance":
        address = params.get("address")
        if not address:
             raise HTTPException(status_code=400, detail="Missing address parameter for get_balance intent.")
        api_path = "/api/v2/scan/accounts"
        request_body = {"address": address}
    elif intent == "get_extrinsic":
        extrinsic_hash = params.get("hash")
        if not extrinsic_hash:
            raise HTTPException(status_code=400, detail="Missing hash parameter for get_extrinsic intent.")
        api_path = "/api/scan/extrinsic"
        request_body = {"hash": extrinsic_hash}
    elif intent == "get_latest_block":
        api_path = "/api/scan/blocks"
        request_body = {"page": 0, "row": 1}
    else:
        raise HTTPException(status_code=400, detail=f"Intent '{intent}' is not supported by the Subscan client.")

    url = f"{base_url}{api_path}"
    print(f"Calling Subscan API: {method} {url} Body: {request_body}")

    try:
        if method == "POST":
             response = await client.post(url, headers=headers, json=request_body)
        else: # GET
             response = await client.get(url, headers=headers) # Add params=request_body if GET uses query params

        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
             error_message = data.get('message', 'Unknown Subscan API error')
             print(f"Subscan API returned error code {data.get('code')}: {error_message}")
             raise HTTPException(status_code=400, detail=f"Subscan API Error: {error_message}")

        print(f"Subscan API Response Code: {data.get('code')}")
        return data
    except httpx.RequestError as e:
        print(f"Network error calling {url}: {e}")
        raise HTTPException(status_code=503, detail=f"Network error calling Subscan API: {e}")
    # HTTPStatusError will be propagated and caught by the main handler