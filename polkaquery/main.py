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
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Body
from substrateinterface import SubstrateInterface
import httpx

from polkaquery.config import settings
from polkaquery.core.resource_manager import ResourceManager
from polkaquery.core.network_config import SUPPORTED_NETWORKS, DEFAULT_NETWORK
from polkaquery.core.formatter import format_subscan_response_for_llm, format_assethub_response_for_llm
from polkaquery.data_sources.subscan_client import call_subscan_api
from polkaquery.data_sources.assethub_rpc_client import execute_assethub_rpc_query
from polkaquery.intent_recognition.llm_based.gemini_recognizer import recognize_intent_with_gemini_llm

# --- Global Resource Manager ---
# This single instance will be used throughout the application's lifecycle.
resource_manager = ResourceManager(settings=settings)
# ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    Initializes resources on startup and cleans them up on shutdown.
    """
    print("INFO: Polkaquery application starting up...")
    # On startup, trigger the ResourceManager to load/generate all tools.
    await resource_manager.load_tools()
    print(f"INFO: Tool loading complete. Subscan tools: {len(resource_manager.subscan_tools)}, AssetHub tools: {len(resource_manager.assethub_tools)}.")
    
    yield
    
    # --- Shutdown ---
    print("INFO: Polkaquery application shutting down...")
    await resource_manager.shutdown()


app = FastAPI(
    title="Polkaquery LLM",
    description="Polkadot ecosystem search via Subscan & Internet, LLM-driven.",
    version="0.7.0 (Refactored)", 
    lifespan=lifespan 
)

async def perform_internet_search(search_query: str) -> dict:
    """
    Performs an internet search using the Tavily client from the ResourceManager.
    """
    print(f"INFO [main.perform_internet_search]: Performing internet search for: '{search_query}'")
    tavily_client = resource_manager.tavily_client
    
    if tavily_client:
        try:
            print(f"INFO [main.perform_internet_search]: Using TavilyClient to search for: {search_query}")
            response_dict = tavily_client.search(query=search_query, search_depth="advanced", max_results=3, include_answer=True)
            return {
                "code": 0,
                "message": "Tavily search successful",
                "data": {
                    "search_provider": "Tavily",
                    "query_used": search_query,
                    "answer_summary": response_dict.get("answer"),
                    "results": response_dict.get("results", [])
                }
            }
        except Exception as e:
            print(f"ERROR [main.perform_internet_search]: Tavily search failed: {e}")
            traceback.print_exc()
            return {"code": -1, "message": f"Internet search with Tavily failed: {str(e)}", "data": None}
    else:
        print("WARN [main.perform_internet_search]: Tavily client not configured. Returning placeholder.")
        return {
            "code": 0, 
            "message": "Placeholder Internet Search", 
            "data": {
                "search_provider": "Placeholder",
                "query_used": search_query,
                "results": [{"title": "Placeholder Search Result", "content": "Tavily client is not configured."}]
            }
        }

async def generate_final_llm_answer(original_query: str, network_context: str, processed_data: dict, source_type: str) -> str:
    """
    Synthesizes a final natural language answer using the Gemini model from the ResourceManager.
    """
    model = resource_manager.gemini_model
    if not model:
        return "Error: Google Gemini model is not available or configured."

    data_summary_for_prompt = json.dumps(processed_data, indent=2)
    if len(data_summary_for_prompt) > 25000: 
        data_summary_for_prompt = data_summary_for_prompt[:25000] + "\n... (data truncated)"

    prompt = f"""
    You are Polkaquery, an AI assistant for the Polkadot ecosystem.
    You have received a user query and processed data. Your task is to synthesize a concise, helpful, and natural language answer.
    Original User Query: "{original_query}"
    Network Context: "{network_context}"
    Data Source Type: "{source_type}" 
    Processed Data:
    ```json
    {data_summary_for_prompt}
    ```
    Based on the original query and the provided data, generate a friendly and informative answer.
    - If the data source is 'Subscan' or 'AssetHub', it's on-chain data. Present it clearly.
    - If the data source is 'InternetSearch', summarize the findings. If there's a direct answer summary, prioritize that.
    - If the data indicates 'not found' or an error, explain it politely.
    - Do not just repeat the JSON. Formulate proper sentences.
    Final Answer:
    """
    try:
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"ERROR [main.generate_final_llm_answer]: Final LLM answer synthesis failed: {e}")
        traceback.print_exc()
        return f"Could not generate a natural language summary. Raw data: {data_summary_for_prompt}"

async def _process_llm_query_logic(raw_query: str, network_name_input: str, network_name_lower:str):
    network_config = SUPPORTED_NETWORKS[network_name_lower]
    processed_data_for_final_llm = None
    data_source_type = "Unknown"
    selected_intent_tool_name = "N/A"

    try:
        print(f"DEBUG [main._process_llm_query_logic]: Raw query='{raw_query}', Network='{network_name_lower}'")
        
        # Select tools based on network
        is_assethub = network_name_lower == "assethub-polkadot-rpc"
        tools_for_llm = list(resource_manager.assethub_tools.values()) if is_assethub else list(resource_manager.subscan_tools.values())

        intent_tool_name, params = await recognize_intent_with_gemini_llm(
            query=raw_query, 
            network_name=network_name_lower,
            model=resource_manager.gemini_model,
            available_tools=tools_for_llm
        )
        selected_intent_tool_name = intent_tool_name
        print(f"DEBUG [main._process_llm_query_logic]: Recognized intent/tool='{intent_tool_name}', params={params}")

        if intent_tool_name == "unknown":
            reason = params.get("reason", "Could not understand query.")
            return {"answer": f"Sorry, I couldn't process that request. Reason: {reason}", "network": network_name_input, "debug_intent": intent_tool_name, "debug_params": params}

        if intent_tool_name == "internet_search":
            data_source_type = "InternetSearch"
            search_query = params.get("search_query", raw_query)
            api_response_json = await perform_internet_search(search_query)
            processed_data_for_final_llm = format_subscan_response_for_llm(
                intent_tool_name, api_response_json, network_name_lower, 0, "", params
            )
        elif is_assethub:
            data_source_type = "AssetHub"
            tool_def = resource_manager.assethub_tools.get(intent_tool_name)
            if not tool_def:
                raise ValueError(f"Tool definition '{intent_tool_name}' not found in ResourceManager.")
            
            api_response_json = execute_assethub_rpc_query(
                substrate_client=resource_manager.assethub_rpc_client,
                tool_definition=tool_def,
                params=params
            )
            processed_data_for_final_llm = format_assethub_response_for_llm(
                api_response_json, intent_tool_name, params
            )
        else: # Subscan
            data_source_type = "Subscan"
            tool_def = resource_manager.subscan_tools.get(intent_tool_name)
            if not tool_def:
                raise ValueError(f"Tool definition '{intent_tool_name}' not found in ResourceManager.")

            api_response_json = await call_subscan_api(
                client=resource_manager.http_client,
                base_url=settings.subscan_base_url,
                tool_definition=tool_def,
                params=params,
                api_key=settings.subscan_api_key
            )
            processed_data_for_final_llm = format_subscan_response_for_llm(
                intent_tool_name, api_response_json, network_name_lower, 
                network_config["decimals"], network_config["symbol"], params
            )

        final_answer = await generate_final_llm_answer(raw_query, network_name_input, processed_data_for_final_llm, data_source_type)

        return {
            "answer": final_answer,
            "network": network_name_input,
            "debug_intent": intent_tool_name,
            "debug_params": params,
            "debug_formatted_data": processed_data_for_final_llm
        }
    except Exception as e:
        traceback.print_exc()
        return {"answer": f"An unexpected internal server error occurred processing tool '{selected_intent_tool_name}': {str(e)}", "network": network_name_input}

@app.post("/llm-query/")
async def handle_llm_query(query_body: dict = Body(...)):
    raw_query = query_body.get("query")
    if not raw_query:
        raise HTTPException(status_code=400, detail="Query field is missing.")

    network_name_input = query_body.get("network", DEFAULT_NETWORK)
    raw_query_lower = raw_query.lower()

    # Route to AssetHub if keywords are present and not overridden by 'subscan'
    if "subscan" not in raw_query_lower:
        rpc_keywords = ["assethub", "statemint", "statemine"]
        if any(keyword in raw_query_lower for keyword in rpc_keywords):
            network_name_input = "assethub-polkadot-rpc"

    network_name_lower = network_name_input.lower()
    if network_name_lower not in SUPPORTED_NETWORKS:
        raise HTTPException(status_code=400, detail=f"Unsupported network: '{network_name_input}'. Supported: {list(SUPPORTED_NETWORKS.keys())}")

    # Verify that the required client for the selected network is available
    if network_name_lower == "assethub-polkadot-rpc" and not resource_manager.assethub_rpc_client:
        raise HTTPException(status_code=503, detail="AssetHub RPC client is not available or configured.")

    return await _process_llm_query_logic(raw_query, network_name_input, network_name_lower)

