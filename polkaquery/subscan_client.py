# subscan_client.py
import httpx
from fastapi import HTTPException

# todo: find exact Subscan API v2 endpoints and their request/response structures for these intents

async def call_subscan_api(client: httpx.AsyncClient, base_url: str, intent: str, params: dict, api_key: str | None) -> dict:
    """
    Calls the appropriate Subscan API endpoint based on the intent.
    """
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
        headers["Content-Type"] = "application/json" # Often needed for POST

    api_path = ""
    request_body = None # For POST requests
    method = "GET" # Default to GET

    # --- Determine Endpoint based on Intent ---
    if intent == "get_balance":
        address = params.get("address")
        if not address:
             raise HTTPException(status_code=400, detail="Missing address parameter for get_balance intent.")
        # Example: Subscan API for account info (Check actual docs!)
        # This might be a POST request in v2
        api_path = "/api/v2/scan/accounts" # V2 endpoint example
        method = "POST"
        request_body = {"address": address} # Example V2 payload

    elif intent == "get_extrinsic":
        extrinsic_hash = params.get("hash")
        if not extrinsic_hash:
            raise HTTPException(status_code=400, detail="Missing hash parameter for get_extrinsic intent.")
        # Example: Subscan API path for extrinsic (Check actual docs!)
        api_path = "/api/scan/extrinsic" # Example V1 endpoint
        method = "POST" # V1 uses POST here
        request_body = {"hash": extrinsic_hash}

    elif intent == "get_latest_block":
        # Example: Subscan API path for blocks (Check actual docs!)
        api_path = "/api/scan/blocks" # This might fetch multiple blocks
        method = "POST" # V1 uses POST
        request_body = {"page": 0, "row": 1} # Fetch just the latest one
        # V2 might have a simpler dedicated endpoint
    else:
        raise HTTPException(status_code=400, detail=f"Intent '{intent}' is not supported by the Subscan client yet.")

    # --- Make the API Call ---
    url = f"{base_url}{api_path}"
    try:
        if method == "POST":
             response = await client.post(url, headers=headers, json=request_body)
        else: # GET
             response = await client.get(url, headers=headers) # Add params= if needed for GET

        response.raise_for_status() # Raise exception for 4xx or 5xx errors
        data = response.json()

        # Subscan specific check (often includes a status code in the JSON body)
        if data.get("code") != 0:
             raise HTTPException(status_code=400, detail=f"Subscan API Error: {data.get('message', 'Unknown error')}")

        return data # Return the full JSON response data

    except httpx.RequestError as e:
        # Network errors, DNS errors etc.
        raise HTTPException(status_code=503, detail=f"Network error calling Subscan API: {e}")
    # We let HTTPStatusError be caught by the main handler to return Subscan's specific error code/message