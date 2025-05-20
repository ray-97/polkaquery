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


import os
from fastapi import FastAPI, HTTPException, Body
from dotenv import load_dotenv
import httpx
import google.generativeai as genai

from polkaquery.intent_recognizer import recognize_intent
from polkaquery.data_sources.subscan_client import call_subscan_api
from polkaquery.core.formatter import format_response

# Load environment variables (e.g., for API keys)
load_dotenv()
SUBSCAN_API_KEY = os.getenv("SUBSCAN_API_KEY")

# --- Network Configuration ---
# Map user-friendly names to Subscan base URLs and token decimals
# Add more networks as needed, verifying their base URLs and decimals
SUPPORTED_NETWORKS = {
    "polkadot": {"base_url": "https://polkadot.api.subscan.io", "decimals": 10, "symbol": "DOT"},
    # "kusama": {"base_url": "https://kusama.api.subscan.io", "decimals": 12, "symbol": "KSM"},
    # "westend": {"base_url": "https://westend.api.subscan.io", "decimals": 12, "symbol": "WND"},
    # Add parachains like Acala, Moonbeam, etc.
    # "acala": {"base_url": "https://acala.api.subscan.io", "decimals": 12, "symbol": "ACA"},
}
DEFAULT_NETWORK = "polkadot"
# --- End Network Configuration ---

app = FastAPI(
    title="Polkaquery",
    description="A Web3 search engine for the Polkadot ecosystem.",
    version="0.1.0"
)

# Create a single httpx client for reuse
http_client = httpx.AsyncClient(timeout=20.0)

@app.on_event("startup")
async def startup_event():
    if not SUBSCAN_API_KEY:
        print("Warning: SUBSCAN_API_KEY environment variable not set. Subscan API calls might fail.")
    pass

@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose()


@app.post("/query/")
async def handle_query(query_body: dict = Body(...)):
    """
    Accepts a natural language query about the Polkadot ecosystem
    and attempts to answer it.

    Body format:
    {
        "query": "Your natural language query",
        "network": "polkadot" (optional, defaults to 'polkadot')
    }
    """
    raw_query = query_body.get("query")
    if not raw_query:
        raise HTTPException(status_code=400, detail="Query field is missing.")

    try:
        # 1. Recognize Intent
        intent, params = recognize_intent(raw_query)

        if intent == "unknown":
            raise HTTPException(status_code=400, detail="Could not understand the query or missing required parameters.")

        # 2. Call Subscan API based on intent
        # The base URL might vary depending on the specific Polkadot/Kusama/Parachain network
        # We'll need to configure this, potentially based on the query or a default
        subscan_base_url = "https://polkadot.api.subscan.io" # Example for Polkadot Mainnet

        subscan_response_json = await call_subscan_api(
            client=http_client,
            base_url=subscan_base_url,
            intent=intent,
            params=params,
            api_key=SUBSCAN_API_KEY
        )

        # 3. Format the response
        formatted_result = format_response(intent, subscan_response_json)

        return {"answer": formatted_result}

    except httpx.HTTPStatusError as e:
        # Handle errors specifically from Subscan or network issues
        raise HTTPException(status_code=e.response.status_code, detail=f"Error calling Subscan API: {e.response.text}")
    except HTTPException as e:
        # Re-raise exceptions we've already shaped
        raise e
    except Exception as e:
        # Catch-all for unexpected errors during processing
        print(f"Unexpected error: {e}") # Log the full error for debugging
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

# Add command to run the server: uvicorn main:app --reload