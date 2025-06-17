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
from contextlib import asynccontextmanager 
import google.generativeai as genai 
import traceback # For printing full tracebacks
from substrateinterface import SubstrateInterface

# Attempt to import TavilyClient
try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None # Set to None if not installed
    print("Warning: TavilyClient not found. Please install with 'pip install tavily-python'. Internet search will use placeholders.")


load_dotenv()
SUBSCAN_API_KEY = os.getenv("SUBSCAN_API_KEY")
ONFINALITY_API_KEY= os.getenv("ONFINALITY_API_KEY")
GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") # For Tavily integration

from polkaquery.core.network_config import SUPPORTED_NETWORKS, DEFAULT_NETWORK
from polkaquery.core.formatter import format_subscan_response_for_llm, format_assethub_response_for_llm
from polkaquery.data_sources.subscan_client import call_subscan_api
from polkaquery.data_sources.assethub_rpc_client import execute_assethub_rpc_query
from polkaquery.intent_recognition.llm_based.gemini_recognizer import recognize_intent_with_gemini_llm

# --- Tavily Client Initialization ---
tavily_client = None
if TAVILY_API_KEY and TavilyClient: # Check if TavilyClient was imported successfully
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        print("TavilyClient initialized successfully.")
    except Exception as e:
        print(f"Error initializing TavilyClient: {e}. Internet search might use placeholders.")
        tavily_client = None # Ensure it's None if initialization fails
elif not TavilyClient:
    pass # Warning already printed at import time
else: # TavilyClient is available but no API key
    print("Warning: TAVILY_API_KEY not set. Internet search will use placeholders.")
# --- End Tavily Client Initialization ---


async def perform_internet_search(search_query: str) -> dict:
    """
    Performs an internet search using Tavily or another search API.
    Returns a dictionary suitable for format_subscan_response_for_llm.
    """
    print(f"Performing internet search for: '{search_query}'")
    if tavily_client: # Check if client was initialized
        try:
            # Using Tavily's async search method if available, otherwise adapt
            # The TavilyClient's search method might be synchronous by default.
            # For an async FastAPI app, ideally use an async-compatible search call.
            # If TavilyClient.search is sync, you might run it in a thread pool:
            # from fastapi.concurrency import run_in_threadpool
            # response_dict = await run_in_threadpool(tavily_client.search, query=search_query, search_depth="advanced", max_results=3)
            
            # Assuming TavilyClient().search is synchronous for this example:
            # For a truly async operation, Tavily would need an async client or you'd use a thread.
            # Let's proceed with the synchronous call for now, but be mindful of potential blocking.
            # The Tavily Python SDK's search method is indeed synchronous.
            # To avoid blocking the FastAPI event loop, it should be run in a thread pool.
            # However, for simplicity in this step, I'll call it directly.
            # In a production system, use `await asyncio.to_thread(tavily_client.search, ...)` or similar.
            
            # For now, let's assume a direct call for demonstration, but highlight this is blocking.
            # In a real async app, this should be:
            # import asyncio
            # response_dict = await asyncio.to_thread(tavily_client.search, query=search_query, search_depth="advanced", max_results=3)
            
            print(f"Using TavilyClient to search for: {search_query}")
            response_dict = tavily_client.search(query=search_query, search_depth="advanced", max_results=3, include_answer=True)
            # Tavily response structure:
            # {
            #   "query": "...",
            #   "follow_up_questions": ["...", "..."],
            #   "answer": "...",
            #   "images": ["...", "..."],
            #   "results": [
            #     {"title": "...", "url": "...", "content": "...", "score": ..., "raw_content": "..."},
            #     ...
            #   ],
            #   "response_time": ...
            # }
            
            return {
                "code": 0, # Simulate Subscan-like success code
                "message": "Tavily search successful",
                "data": {
                    "search_provider": "Tavily",
                    "query_used": search_query,
                    "answer_summary": response_dict.get("answer"), # Tavily might provide a direct answer
                    "results": response_dict.get("results", []) # Pass through the list of results
                }
            }
        except Exception as e:
            print(f"Error during Tavily search: {e}")
            traceback.print_exc()
            return {"code": -1, "message": f"Internet search with Tavily failed: {str(e)}", "data": None}
    else:
        # Fallback to placeholder if Tavily is not configured
        print("Warning: Tavily client not configured or API key missing. Internet search returning placeholder.")
        return {
            "code": 0, 
            "message": "Placeholder Internet Search", 
            "data": {
                "search_provider": "Placeholder",
                "query_used": search_query,
                "results": [
                    {"title": "Placeholder Search Result", 
                     "url": "http://example.com",
                     "content": f"This is a placeholder search result for the query: '{search_query}'. Tavily client is not configured."}
                ]
            }
        }
# --- End Internet Search Client ---

# --- Globals for client instances ---
http_client_instance: httpx.AsyncClient | None = None
assethub_rpc_client_instance: SubstrateInterface | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):

    if not SUBSCAN_API_KEY: print("Warning: SUBSCAN_API_KEY not set.")
    global http_client_instance
    print("Application startup: Initializing HTTP client...")
    http_client_instance = httpx.AsyncClient(timeout=20.0)


    if not ONFINALITY_API_KEY: print("Warning: ONFINALITY_API_KEY not set.")
    global assethub_rpc_client_instance
    if ONFINALITY_API_KEY:
        assethub_ws_url = f"wss://statemint.api.onfinality.io/ws?apikey={ONFINALITY_API_KEY}"
        try:
            assethub_rpc_client_instance = SubstrateInterface(url=assethub_ws_url)
            assethub_rpc_client_instance.init_runtime()
            print(f"INFO: AssetHub RPC client connected via API Key.")
        except Exception as e:
            print(f"CRITICAL ERROR: Could not connect AssetHub RPC client on startup. Error: {e}")
            traceback.print_exc()
            assethub_rpc_client_instance = None # Ensure it's None on failure
    else:
        print("WARNING: ONFINALITY_API_KEY not found. AssetHub RPC client not initialized.")

    if GOOGLE_GEMINI_API_KEY:
        try:
            genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
            print("Google Gemini API configured successfully.")
        except Exception as e: print(f"Error configuring Google Gemini API: {e}")
    else: print("Warning: GOOGLE_GEMINI_API_KEY not set.")

    if not TAVILY_API_KEY: 
        print("Warning: TAVILY_API_KEY not set. Internet search will use placeholders.")
    elif not TavilyClient:
        print("Warning: TavilyClient library not installed. Internet search will use placeholders.")
    elif not tavily_client: # If TavilyClient is imported but instance is None (init failed)
        print("Warning: TavilyClient initialization failed. Internet search will use placeholders.")

    print("Polkaquery application started.")
    yield

    # --- Shutdown ---
    if http_client_instance:
        await http_client_instance.aclose()
        print("INFO: HTTP client shut down.")
        
    if assethub_rpc_client_instance and assethub_rpc_client_instance.websocket:
        assethub_rpc_client_instance.close()
        print("INFO: AssetHub RPC client connection closed.")

app = FastAPI(
    title="Polkaquery LLM",
    description="Polkadot ecosystem search via Subscan & Internet, LLM-driven.",
    version="0.6.1 (Tavily Configured)", 
    lifespan=lifespan 
)

async def generate_final_llm_answer(original_query: str, network_context: str, processed_data: dict, source_type: str) -> str:
    if not GOOGLE_GEMINI_API_KEY:
        return "Error: Google Gemini API Key not configured."

    model = genai.GenerativeModel('gemini-1.5-flash') 
    data_summary_for_prompt = json.dumps(processed_data, indent=2)
    # Increased truncation limit slightly, ensure it's reasonable for Gemini context window
    if len(data_summary_for_prompt) > 25000: 
        data_summary_for_prompt = data_summary_for_prompt[:25000] + "\n... (data truncated)"

    prompt = f"""
    You are Polkaquery, an AI assistant for the Polkadot ecosystem.
    You have received a user query and processed data.
    Your task is to synthesize a concise, helpful, and natural language answer.

    Original User Query: "{original_query}"
    Network Context (if applicable for Subscan data): "{network_context}"
    Data Source Type: "{source_type}" 

    Processed Data (contains key information or search results):
    ```json
    {data_summary_for_prompt}
    ```

    Based on the original query and the provided data, generate a friendly and informative answer.
    - If the data source is 'Subscan', it's on-chain data. Present it clearly and accurately.
    - If the data source is 'InternetSearch' (e.g., from Tavily), it's from a web search. Summarize the findings, and if there's a direct answer summary from the search tool (like Tavily's 'answer_summary'), prioritize that. Also, mention key search result titles or snippets if relevant.
    - If the data indicates 'not found' or an error, explain it politely.
    - Do not just repeat the JSON. Formulate proper sentences/paragraphs.
    - Be concise but complete.

    Final Answer:
    """
    try:
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error during final LLM answer synthesis: {e}")
        traceback.print_exc()
        return f"Could not generate a natural language summary. Raw data summary: {data_summary_for_prompt}"

async def _process_llm_query_logic(
    raw_query: str, network_name_input: str, network_name_lower:str,
    client: httpx.AsyncClient, substrate_rpc_client: SubstrateInterface
):
    network_config = SUPPORTED_NETWORKS[network_name_lower]
    decimals = network_config["decimals"]
    symbol = network_config["symbol"]

    if network_name_lower != "assethub-polkadot-rpc":
        subscan_base_url = network_config["base_url"]
    
    processed_data_for_final_llm = None
    data_source_type = "Unknown"
    # This variable will hold the name of the tool selected by the first LLM call
    # It's used for error messages and debugging.
    selected_intent_tool_name = "N/A" 

    try:
        print(f"DEBUG [main._process_llm_query_logic]: Raw query='{raw_query}', Network='{network_name_lower}'")
        intent_tool_name, params = await recognize_intent_with_gemini_llm(raw_query, network_name_lower)
        selected_intent_tool_name = intent_tool_name # Store for later use in error messages
        print(f"DEBUG [main._process_llm_query_logic]: Recognized intent/tool='{intent_tool_name}', params={params}")

        if intent_tool_name == "unknown":
            reason = params.get("reason", "Could not understand query or missing parameters.")
            return {"answer": f"Sorry, I couldn't process that request. Reason: {reason}", 
                    "network": network_name_input, "debug_intent": intent_tool_name, "debug_params": params}

        if intent_tool_name == "internet_search":
            data_source_type = "InternetSearch"
            search_query_for_tool = params.get("search_query", raw_query) 
            api_response_json = await perform_internet_search(search_query_for_tool)
            
            processed_data_for_final_llm = format_subscan_response_for_llm(
                intent_tool_name=intent_tool_name, 
                subscan_data=api_response_json, 
                network_name=network_name_lower, 
                decimals=0, 
                symbol="",   
                original_params=params
            )
        elif network_name_lower == "polkadot" and intent_tool_name and intent_tool_name != "unknown": 
            data_source_type = "Subscan"
            api_response_json = await call_subscan_api(
                client=client, 
                base_url=subscan_base_url,
                intent_tool_name=intent_tool_name,
                params=params,
                api_key=SUBSCAN_API_KEY
            )
            processed_data_for_final_llm = format_subscan_response_for_llm(
                intent_tool_name=intent_tool_name,
                subscan_data=api_response_json,
                network_name=network_name_lower,
                decimals=decimals,
                symbol=symbol,
                original_params=params
            )
        elif network_name_lower == "assethub-polkadot-rpc" and intent_tool_name and intent_tool_name != "unknown":
            api_response_json = execute_assethub_rpc_query(
                substrate_client=substrate_rpc_client,
                intent_tool_name=intent_tool_name,
                params=params
            )
            processed_data_for_final_llm = format_assethub_response_for_llm(
                api_response_json, 
                intent_tool_name, 
                params
            )
        else: 
             # This case should ideally be caught by the "unknown" check above
             # or by the recognizer returning an error if the tool name is invalid.
             print(f"Error: Unexpected tool name received: {intent_tool_name}")
             return {"answer": f"An internal error occurred with tool selection ('{intent_tool_name}').", 
                     "network": network_name_input}


        final_answer = await generate_final_llm_answer(raw_query, network_name_input, processed_data_for_final_llm, data_source_type)

        return {
            "answer": final_answer,
            "network": network_name_input,
            "debug_intent": intent_tool_name,
            "debug_params": params,
            "debug_formatted_data": processed_data_for_final_llm
            }

    except httpx.HTTPStatusError as e:
        error_detail = f"Error calling API for '{selected_intent_tool_name}' on network '{network_name_input}': Status {e.response.status_code}"
        try:
            api_error = e.response.json()
            error_detail += f" - {api_error.get('message', e.response.text)}"
        except Exception: error_detail += f" - {e.response.text}"
        return {"answer": f"There was an issue fetching data: {error_detail}", "network": network_name_input}
    except httpx.RequestError as e:
         return {"answer": f"Network error connecting for '{selected_intent_tool_name}' on network '{network_name_input}': {e}", "network": network_name_input}
    except HTTPException as e: 
        return {"answer": f"Input error: {e.detail}", "network": network_name_input}
    except Exception as e:
        traceback.print_exc() 
        return {"answer": f"An unexpected internal server error occurred processing tool '{selected_intent_tool_name}': {str(e)}", "network": network_name_input}

@app.post("/llm-query/")
async def handle_llm_query(query_body: dict = Body(...)):
    """
    Handles a natural language query about the Polkadot ecosystem,
    routes it to the appropriate data source, executes the query,
    and returns a formatted natural language response.
    """

    raw_query = query_body.get("query")

    network_name_input = query_body.get("network", DEFAULT_NETWORK) # network for fetching data
    if not raw_query: raise HTTPException(status_code=400, detail="Query field is missing.")

    # Define keywords that indicate the query is about AssetHub.
    rpc_keywords = ["assethub", "statemint", "statemine"]
    if any(keyword in raw_query.lower() for keyword in rpc_keywords):
        network_name_input = "assethub-polkadot-rpc"

    network_name_lower = network_name_input.lower()
    if network_name_lower not in SUPPORTED_NETWORKS:
        raise HTTPException(status_code=400, detail=f"Unsupported network: '{network_name_input}'. Supported: {list(SUPPORTED_NETWORKS.keys())}")
    
    is_rpc_network = network_name_lower == "assethub-polkadot-rpc"

    if not is_rpc_network and not http_client_instance:
        print("CRITICAL ERROR: HTTP client not initialized.")
        async with httpx.AsyncClient(timeout=20.0) as fallback_client:
             return await _process_llm_query_logic(raw_query, network_name_input, network_name_lower, fallback_client, None)

    if is_rpc_network and not assethub_rpc_client_instance:
        raise HTTPException(status_code=503, detail="AssetHub RPC client is not available. Please try again later.")

    return await _process_llm_query_logic(
        raw_query, network_name_input, network_name_lower, http_client_instance, assethub_rpc_client_instance)

