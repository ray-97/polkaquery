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
import asyncio
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
from polkaquery.routing import route_query_with_llm
from polkaquery.core.async_cache import async_cached, api_cache

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

@async_cached(api_cache)
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

    prompt = resource_manager.final_answer_prompt.format(
        original_query=original_query,
        network_context=network_context,
        source_type=source_type,
        data_summary_for_prompt=data_summary_for_prompt
    )
    try:
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"ERROR [main.generate_final_llm_answer]: Final LLM answer synthesis failed: {e}")
        traceback.print_exc()
        return f"Could not generate a natural language summary. Raw data: {data_summary_for_prompt}"

async def _process_llm_query_logic(raw_query: str, network_name_input: str):
    processed_data_for_final_llm = None
    data_source_type = "Unknown"
    selected_intent_tool_name = "N/A"

    try:
        # Step 1: Use the LLM Router to decide the data source
        chosen_route = await route_query_with_llm(
            query=raw_query,
            model=resource_manager.gemini_model,
            prompt_template=resource_manager.router_prompt
        )
        print(f"DEBUG [main._process_llm_query_logic]: LLM-Router chose route: '{chosen_route}'")

        # Step 2: Execute based on the chosen route
        if chosen_route == "internet_search":
            data_source_type = "InternetSearch"
            # For internet search, we can bypass the tool recognizer and call it directly.
            # The search query can be the raw query itself.
            selected_intent_tool_name = "internet_search"
            api_response_json = await perform_internet_search(raw_query)
            processed_data_for_final_llm = format_subscan_response_for_llm(
                selected_intent_tool_name, api_response_json, network_name_input, 0, "", {"search_query": raw_query}
            )

        else: # This handles 'subscan' and 'assethub' routes
            if chosen_route == 'assethub':
                data_source_type = "AssetHub"
                tools_for_llm = list(resource_manager.assethub_tools.values())
                prompt_template = resource_manager.assethub_recognizer_prompt
                network_name_lower = "assethub-polkadot-rpc"
            else: # Default to subscan
                data_source_type = "Subscan"
                tools_for_llm = list(resource_manager.subscan_tools.values())
                prompt_template = resource_manager.tool_recognizer_prompt
                network_name_lower = network_name_input.lower()

            # Step 2a: Use the Tool Recognizer LLM
            intent_tool_name, params = await recognize_intent_with_gemini_llm(
                query=raw_query, 
                model=resource_manager.gemini_model,
                available_tools=tools_for_llm,
                prompt_template=prompt_template
            )
            selected_intent_tool_name = intent_tool_name
            print(f"DEBUG [main._process_llm_query_logic]: Recognized intent/tool='{intent_tool_name}', params={params}")

            if intent_tool_name == "unknown":
                reason = params.get("reason", "Could not understand query.")
                return {"answer": f"Sorry, I couldn't process that request. Reason: {reason}", "network": network_name_input, "debug_intent": intent_tool_name, "debug_params": params}

            # Step 2b: Execute the chosen tool
            if data_source_type == "AssetHub":
                tool_def = resource_manager.assethub_tools.get(intent_tool_name)
                if not tool_def: raise ValueError(f"Tool '{intent_tool_name}' not found in ResourceManager.")
                # Run the synchronous, cached function in a thread to avoid blocking the event loop
                api_response_json = await asyncio.to_thread(
                    execute_assethub_rpc_query,
                    substrate_client=resource_manager.assethub_rpc_client,
                    tool_definition=tool_def,
                    params=params
                )
                processed_data_for_final_llm = format_assethub_response_for_llm(
                    api_response_json, intent_tool_name, params
                )
            else: # Subscan
                tool_def = resource_manager.subscan_tools.get(intent_tool_name)
                if not tool_def: raise ValueError(f"Tool '{intent_tool_name}' not found in ResourceManager.")
                network_config = SUPPORTED_NETWORKS[network_name_lower]
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

        # Step 3: Generate Final Answer
        final_answer = await generate_final_llm_answer(raw_query, network_name_input, processed_data_for_final_llm, data_source_type)

        return {
            "answer": final_answer,
            "network": network_name_input,
            "debug_intent": selected_intent_tool_name,
            "debug_params": getattr(selected_intent_tool_name, 'params', {}),
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

    # Network name is still accepted but its primary role in routing is diminished.
    # It's now mainly used for context with the Subscan client.
    network_name_input = query_body.get("network", DEFAULT_NETWORK)
    network_name_lower = network_name_input.lower()
    if network_name_lower not in SUPPORTED_NETWORKS:
        raise HTTPException(status_code=400, detail=f"Unsupported network: '{network_name_input}'. Supported: {list(SUPPORTED_NETWORKS.keys())}")

    return await _process_llm_query_logic(raw_query, network_name_input)

