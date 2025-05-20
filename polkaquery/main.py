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

# Load environment variables (e.g., for API keys)
load_dotenv()
SUBSCAN_API_KEY = os.getenv("SUBSCAN_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") # For Gemini, checked by gemini_recognizer

from polkaquery.core.network_config import SUPPORTED_NETWORKS, DEFAULT_NETWORK
from polkaquery.core.formatter import format_response
from polkaquery.data_sources.subscan_client import call_subscan_api
from polkaquery.intent_recognition.rule_based.recognizer import recognize_intent_rules
from polkaquery.intent_recognition.llm_based.gemini_recognizer import recognize_intent_with_gemini_llm

app = FastAPI(
    title="Polkaquery",
    description="A Web3 search engine for the Polkadot ecosystem, providing data using rule-based and LLM-based intent recognition.",
    version="0.1.0"
)

# Create a single httpx client for reuse
http_client = httpx.AsyncClient(timeout=20.0)

@app.on_event("startup")
async def startup_event():
    """Handles application startup events."""
    if not SUBSCAN_API_KEY:
        print("Warning: SUBSCAN_API_KEY environment variable not set. Subscan API calls might fail.")
    if not GOOGLE_API_KEY:
        print("Warning: GOOGLE_API_KEY environment variable not set. LLM queries will fail.")
    # Initialize other resources if needed
    pass

@app.on_event("shutdown")
async def shutdown_event():
    """Handles application shutdown events."""
    await http_client.aclose()

async def process_query_request(raw_query: str, network_name: str, intent_recognizer_func, is_llm: bool):
    """
    Central logic to process a query using a specified intent recognizer.
    Args:
        raw_query: The user's natural language query.
        network_name: The target network name.
        intent_recognizer_func: The function to use for intent recognition.
        is_llm: Boolean, true if the recognizer is LLM-based (needs network_name context).
    """
    if not raw_query:
        raise HTTPException(status_code=400, detail="Query field is missing.")

    network_name_lower = network_name.lower()
    if network_name_lower not in SUPPORTED_NETWORKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported network: '{network_name_lower}'. Supported networks are: {list(SUPPORTED_NETWORKS.keys())}"
        )
    network_config = SUPPORTED_NETWORKS[network_name_lower]
    subscan_base_url = network_config["base_url"]
    decimals = network_config["decimals"]
    symbol = network_config["symbol"]

    try:
        if is_llm: # LLM recognizer expects network_name
            intent, params = await intent_recognizer_func(raw_query, network_name_lower)
        else: # Rule-based recognizer does not expect network_name
            intent, params = intent_recognizer_func(raw_query)


        if intent == "unknown":
            reason = params.get("reason", "Could not understand the query or missing required parameters.")
            raise HTTPException(status_code=400, detail=reason)

        subscan_response_json = await call_subscan_api(
            client=http_client,
            base_url=subscan_base_url,
            intent=intent,
            params=params,
            api_key=SUBSCAN_API_KEY
        )

        formatted_result = format_response(
            intent=intent,
            subscan_data=subscan_response_json,
            network_name=network_name_lower,
            decimals=decimals,
            symbol=symbol,
            params=params # Pass params to formatter for context if needed
        )
        return {"answer": formatted_result, "network": network_name_lower, "intent_used": intent, "parameters_extracted": params}

    except httpx.HTTPStatusError as e:
        error_detail = f"Error calling Subscan API for network '{network_name_lower}': Status {e.response.status_code}"
        try:
            subscan_error = e.response.json()
            error_detail += f" - {subscan_error.get('message', e.response.text)}"
        except Exception:
             error_detail += f" - {e.response.text}"
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.RequestError as e:
         raise HTTPException(status_code=503, detail=f"Network error connecting to Subscan for network '{network_name_lower}': {e}")
    except HTTPException as e: # Re-raise already formatted HTTPExceptions
        raise e
    except Exception as e:
        import traceback
        traceback.print_exc() # Log full traceback for server-side debugging
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")


@app.post("/query/") # Rule-based endpoint
async def handle_rule_query(query_body: dict = Body(...)):
    """
    Handles queries using rule-based intent recognition.
    Body format: {"query": "user's query", "network": "polkadot" (optional)}
    """
    raw_query = query_body.get("query")
    network_name = query_body.get("network", DEFAULT_NETWORK)
    return await process_query_request(raw_query, network_name, recognize_intent_rules, is_llm=False)


@app.post("/llm-query/") # LLM-based endpoint
async def handle_llm_query(query_body: dict = Body(...)):
    """
    Handles queries using LLM-based (Gemini) intent recognition.
    Body format: {"query": "user's query", "network": "polkadot" (optional)}
    """
    raw_query = query_body.get("query")
    network_name = query_body.get("network", DEFAULT_NETWORK)
    return await process_query_request(raw_query, network_name, recognize_intent_with_gemini_llm, is_llm=True)

# To run (from polkaquery_project_root):
# uvicorn polkaquery.main:app --reload