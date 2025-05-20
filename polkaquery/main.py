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

import os
from fastapi import FastAPI, HTTPException, Body
from dotenv import load_dotenv
import httpx
import json
from contextlib import asynccontextmanager # Import for lifespan manager

# Load environment variables at the application start
load_dotenv()
SUBSCAN_API_KEY = os.getenv("SUBSCAN_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- Import from new structure ---
from polkaquery.core.network_config import SUPPORTED_NETWORKS, DEFAULT_NETWORK
from polkaquery.core.formatter import format_response_for_llm
from polkaquery.data_sources.subscan_client import call_subscan_api
from polkaquery.intent_recognition.llm_based.gemini_recognizer import recognize_intent_with_gemini_llm
# --- End Imports ---

# Global httpx client instance - to be managed by lifespan
http_client_instance = None

# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    global http_client_instance
    print("Application startup: Initializing HTTP client...")
    http_client_instance = httpx.AsyncClient(timeout=20.0)
    
    if not SUBSCAN_API_KEY:
        print("Warning: SUBSCAN_API_KEY environment variable not set. Subscan API calls might fail.")
    if not GOOGLE_API_KEY:
        print("Warning: GOOGLE_API_KEY environment variable not set. LLM queries will fail.")
    
    print("Polkaquery application started successfully.")
    yield  # Application runs here
    # Shutdown logic
    print("\nApplication shutdown: Closing HTTP client...")
    if http_client_instance:
        await http_client_instance.aclose()
    print("Polkaquery application shut down gracefully.")

# --- End Lifespan Management ---

app = FastAPI(
    title="Polkaquery LLM",
    description="A Web3 search engine for the Polkadot ecosystem, using LLM-based intent recognition and data retrieval via Subscan API.",
    version="0.5.1 (Lifespan Update)",
    lifespan=lifespan # Use the new lifespan context manager
)


async def generate_final_llm_answer(query: str, network_name: str, formatted_subscan_data: dict) -> str:
    """
    Takes the pre-formatted Subscan data and the original query,
    and asks Gemini to synthesize a final natural language answer.
    """
    if not GOOGLE_API_KEY:
        return "Error: Google API Key not configured for final answer synthesis."

    import google.generativeai as genai # Keep import here to ensure it's configured if needed
    if not genai.API_KEY: 
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
        except Exception as e:
            print(f"Error configuring Gemini in generate_final_llm_answer: {e}")
            return "Error: Could not configure Google API for final answer synthesis."


    model = genai.GenerativeModel('gemini-1.5-flash') 

    data_summary_for_prompt = json.dumps(formatted_subscan_data, indent=2)
    if len(data_summary_for_prompt) > 30000: 
        data_summary_for_prompt = data_summary_for_prompt[:30000] + "\n... (data truncated)"

    prompt = f"""
    You are Polkaquery, an AI assistant for the Polkadot ecosystem.
    You have received a user query and pre-processed data from the Subscan API.
    Your task is to synthesize a concise, helpful, and natural language answer for the user.

    Original User Query: "{query}"
    Target Network: "{network_name}"

    Pre-processed Data from Subscan (summarized or key data points):
    ```json
    {data_summary_for_prompt}
    ```

    Based on the original query and the provided data, generate a friendly and informative answer.
    - If the data directly answers the query, present it clearly.
    - If the data is a list, summarize it or highlight key items relevant to the query.
    - If the data indicates 'not found' or an error that was pre-processed, explain it politely.
    - Do not just repeat the JSON. Formulate a proper sentence or paragraph.
    - If the pre-processed data contains an error message, convey that error appropriately.
    - Be concise but complete.

    Final Answer:
    """
    try:
        response = await model.generate_content_async(prompt)
        final_answer = response.text.strip()
        return final_answer
    except Exception as e:
        print(f"Error during final LLM answer synthesis: {e}")
        return f"Could not generate a natural language summary. Raw data summary: {data_summary_for_prompt}"


@app.post("/llm-query/")
async def handle_llm_query(query_body: dict = Body(...)):
    """
    Handles queries using LLM-based (Gemini) intent recognition,
    data retrieval, pre-formatting, and final LLM-based answer synthesis.
    """
    raw_query = query_body.get("query")
    network_name_input = query_body.get("network", DEFAULT_NETWORK)

    if not raw_query:
        raise HTTPException(status_code=400, detail="Query field is missing.")

    network_name_lower = network_name_input.lower()
    if network_name_lower not in SUPPORTED_NETWORKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported network: '{network_name_input}'. Supported networks are: {list(SUPPORTED_NETWORKS.keys())}"
        )
    
    network_config = SUPPORTED_NETWORKS[network_name_lower]
    subscan_base_url = network_config["base_url"]
    decimals = network_config["decimals"]
    symbol = network_config["symbol"]

    # Ensure http_client_instance is available (should be set by lifespan)
    if not http_client_instance:
        # This case should ideally not happen if lifespan is correctly managed
        print("Error: HTTP client not initialized. Re-initializing for this request (fallback).")
        async with httpx.AsyncClient(timeout=20.0) as fallback_client:
             client_to_use = fallback_client
             return await _process_llm_query_logic(
                raw_query, network_name_input, network_name_lower, network_config,
                subscan_base_url, decimals, symbol, client_to_use
            )
    else:
        client_to_use = http_client_instance
        return await _process_llm_query_logic(
            raw_query, network_name_input, network_name_lower, network_config,
            subscan_base_url, decimals, symbol, client_to_use
        )

async def _process_llm_query_logic(
    raw_query: str, network_name_input: str, network_name_lower:str, network_config: dict,
    subscan_base_url: str, decimals: int, symbol: str, client: httpx.AsyncClient
):
    """Helper function containing the core logic for /llm-query/ endpoint."""
    try:
        intent_tool_name, params = await recognize_intent_with_gemini_llm(raw_query, network_name_lower)

        if intent_tool_name == "unknown":
            reason = params.get("reason", "Could not understand the query or missing required parameters.")
            return {"answer": f"Sorry, I couldn't process that request. Reason: {reason}", 
                    "network": network_name_input, "debug_intent": intent_tool_name, "debug_params": params}

        subscan_response_json = await call_subscan_api(
            client=client, # Use the passed client
            base_url=subscan_base_url,
            intent_tool_name=intent_tool_name,
            params=params,
            api_key=SUBSCAN_API_KEY
        )

        formatted_subscan_data_for_llm = format_response_for_llm(
            intent_tool_name=intent_tool_name,
            subscan_data=subscan_response_json,
            network_name=network_name_lower,
            decimals=decimals,
            symbol=symbol,
            original_params=params
        )
        
        final_answer = await generate_final_llm_answer(raw_query, network_name_input, formatted_subscan_data_for_llm)

        return {
            "answer": final_answer,
            "network": network_name_input,
            "debug_intent": intent_tool_name,
            "debug_params": params,
            "debug_formatted_subscan_data": formatted_subscan_data_for_llm
            }

    except httpx.HTTPStatusError as e:
        error_detail = f"Error calling Subscan API for network '{network_name_input}': Status {e.response.status_code}"
        try:
            subscan_error = e.response.json()
            error_detail += f" - {subscan_error.get('message', e.response.text)}"
        except Exception:
             error_detail += f" - {e.response.text}"
        return {"answer": f"There was an issue fetching data from Subscan: {error_detail}", "network": network_name_input}

    except httpx.RequestError as e:
         return {"answer": f"Network error connecting to Subscan for network '{network_name_input}': {e}", "network": network_name_input}
    
    except HTTPException as e: 
        return {"answer": f"Input error: {e.detail}", "network": network_name_input}

    except Exception as e:
        import traceback
        traceback.print_exc() 
        return {"answer": f"An unexpected internal server error occurred: {str(e)}", "network": network_name_input}

# To run (from polkaquery_project_root):
# uvicorn polkaquery.main:app --reload --port 8000
