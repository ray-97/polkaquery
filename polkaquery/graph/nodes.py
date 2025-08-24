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

import asyncio
import httpx
from langsmith import traceable

from .state import GraphState
from polkaquery.routing import route_query_with_llm
from polkaquery.intent_recognition.llm_based.gemini_recognizer import recognize_intent_with_gemini_llm
from polkaquery.data_sources.subscan_client import call_subscan_api
from polkaquery.data_sources.assethub_rpc_client import execute_assethub_rpc_query
from polkaquery.core.formatter import format_subscan_response_for_llm, format_assethub_response_for_llm
from polkaquery.core.helpers import perform_internet_search, generate_final_llm_answer, generate_error_explanation_with_llm
from polkaquery.core.network_config import SUPPORTED_NETWORKS

# This module defines the functions that will be the nodes of the graph.
# Each function takes the current state and a config object as input
# and returns a dictionary with the fields to update in the state.

@traceable
async def route_query(state: GraphState, config: dict) -> dict:
    """Determines the best data source (route) for the user's query."""
    print("---NODE: route_query---")
    rm = config["configurable"]["resource_manager"]
    chosen_route = await route_query_with_llm(
        query=state["query"],
        model=rm.gemini_model,
        prompt_template=rm.router_prompt
    )
    return {"route": chosen_route}

@traceable
async def recognize_tool(state: GraphState, config: dict) -> dict:
    """Recognizes the specific tool and parameters to use based on the chosen route."""
    print(f"---NODE: recognize_tool (Route: {state['route']})---")
    rm = config["configurable"]["resource_manager"]
    if state['route'] == 'assethub':
        tools = list(rm.assethub_tools.values())
        prompt = rm.assethub_recognizer_prompt
    else: # Default to subscan
        tools = list(rm.subscan_tools.values())
        prompt = rm.tool_recognizer_prompt

    tool_name, params = await recognize_intent_with_gemini_llm(
        query=state["query"],
        model=rm.gemini_model,
        available_tools=tools,
        prompt_template=prompt
    )
    return {"tool_name": tool_name, "tool_params": params}

@traceable
async def execute_tool(state: GraphState, config: dict) -> dict:
    """Executes the chosen tool with the extracted parameters."""
    print(f"---NODE: execute_tool (Tool: {state['tool_name']})---")
    rm = config["configurable"]["resource_manager"]
    route = state["route"]
    tool_name = state["tool_name"]
    params = state["tool_params"]
    api_response = None
    error_message = None

    try:
        if route == "internet_search":
            api_response = await perform_internet_search(rm, state["query"])
        elif route == "assethub":
            tool_def = rm.assethub_tools.get(tool_name)
            if not tool_def: raise ValueError(f"Tool '{tool_name}' not found.")
            api_response = await asyncio.to_thread(
                execute_assethub_rpc_query,
                substrate_client=rm.assethub_rpc_client,
                tool_definition=tool_def,
                params=params
            )
        else: # subscan
            tool_def = rm.subscan_tools.get(tool_name)
            if not tool_def: raise ValueError(f"Tool '{tool_name}' not found.")
            api_response = await call_subscan_api(
                client=rm.http_client,
                base_url=rm.settings.subscan_base_url,
                tool_definition=tool_def,
                params=params,
                api_key=rm.settings.subscan_api_key
            )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            error_message = e.response.json().get("message", "Bad Request")
        else:
            error_message = f"HTTP Error: {e.response.status_code}"
    except Exception as e:
        error_message = str(e)

    return {"api_response": api_response, "error_message": error_message}

@traceable
async def format_response(state: GraphState, config: dict) -> dict:
    """Formats the successful API response into a digestible summary for the final LLM call."""
    print("---NODE: format_response---")
    # This node is a placeholder for now, as the final answer generation
    # can often directly handle the raw JSON. For more complex formatting,
    # this is where the logic from core/formatter.py would be integrated.
    return {}

@traceable
async def generate_answer(state: GraphState, config: dict) -> dict:
    """Generates the final, user-facing natural language answer."""
    print("---NODE: generate_answer---")
    rm = config["configurable"]["resource_manager"]
    final_answer = await generate_final_llm_answer(
        rm,
        original_query=state["query"],
        network_context=state["network"],
        processed_data=state["api_response"],
        source_type=state["route"]
    )
    return {"final_answer": final_answer}

@traceable
async def handle_error(state: GraphState, config: dict) -> dict:
    """Generates a user-friendly explanation for an error."""
    print("---NODE: handle_error---")
    rm = config["configurable"]["resource_manager"]
    final_answer = await generate_error_explanation_with_llm(
        rm,
        original_query=state["query"],
        tool_name=state["tool_name"],
        params=state["tool_params"],
        error_message=state["error_message"]
    )
