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
import google.generativeai as genai
import traceback

def llm_instruction_by_network(network_name: str) -> str:
    if network_name == "assethub-polkadot-rpc":
        return """
        1.  **Analyze the User Query within the Polkadot AssetHub context.** Your primary goal is to match the user's request to a specific on-chain data tool if possible.
        2.  **Prioritize RPC Tools for On-Chain Data.** The available tools (e.g., `assets_asset`, `assets_account`) are for direct RPC queries.
            - If the query contains "asset" and a number (e.g., "asset 1984", "details for asset 1337"), you MUST choose the `assets_asset` tool and extract the number as `key1`.
            - If the query asks for a "balance" of a specific asset for an "account", you MUST choose the `assets_account` tool and extract the asset ID as `key1` and the account address as `key2`.
        3.  **Use `internet_search` ONLY as a fallback.** Only choose `internet_search` if the query is purely conceptual (e.g., "what is an NFT?"), asks for news, or is about a topic with no corresponding on-chain data tool. DO NOT use `internet_search` if a specific data tool fits.
        4.  **Extract Parameters.** You must extract all required parameters for the chosen tool.
        5.  **Respond with JSON only.** Your final output must be a single, valid JSON object in the format: `{"intent": "chosen_tool_name", "parameters": {"param_name": "value"}}`.
        """
    else:
        return """
        Instructions:
        1. Analyze the User Query.
        2. If the query asks for specific on-chain data (balances, extrinsics, blocks, staking info, specific asset details, etc.) that matches a Subscan tool description, choose that tool.
        3. If the query is broad, asks for general explanations, news, concepts (e.g., "what is staking?", "latest Polkadot news", "how do XCM transfers work conceptually?"), or information not directly available as structured on-chain data via Subscan tools, choose the "internet_search" tool.
        4. Extract all necessary parameters for the chosen tool. For "internet_search", the "search_query" parameter should be a well-formulated version of the user's question.
        5. If no tool (neither Subscan nor internet_search) seems appropriate, or if required parameters are missing for an otherwise suitable tool, respond with "intent": "unknown" and a "reason".
        6. Respond ONLY with a single, valid JSON object: {{"intent": "chosen_tool_name", "parameters": {{"param_name": "value"}}}}.
        """
    
async def recognize_intent_with_gemini_llm(
    query: str, 
    network_name: str, 
    model: genai.GenerativeModel, 
    available_tools: list[dict]
) -> tuple[str, dict]:
    if not model:
        return "unknown", {"reason": "Google Gemini model is not available."}
    if not available_tools:
        return "unknown", {"reason": "No API tools (including internet search) loaded for LLM to use."}

    instructions = llm_instruction_by_network(network_name)

    tools_prompt_section = "AVAILABLE TOOLS (CHOOSE ONE):\n"
    for tool in available_tools:
        tools_prompt_section += f"- Name: {tool.get('name', 'Unnamed Tool')}\n"
        tools_prompt_section += f"  Description: {tool.get('description', 'No description.')}\n"
        if tool.get('parameters') and tool['parameters'].get('properties'):
            tools_prompt_section += f"  Parameters Schema: {json.dumps(tool['parameters'])}\n\n"
        else:
            tools_prompt_section += "  Parameters Schema: {}\n\n"

    prompt = f"""
    You are an expert AI assistant for Polkaquery, specializing in the Polkadot ecosystem ({network_name}).
    Your task is to understand user queries, select the most appropriate single tool from AVAILABLE TOOLS,
    and extract parameters for that tool.

    {tools_prompt_section}

    User Query: "{query}"
    Target Network Context: "{network_name}"

    {instructions}

    JSON Response:
    """
    try:
        generation_config = genai.types.GenerationConfig(temperature=0.0)
        response = await model.generate_content_async(prompt, generation_config=generation_config)
        raw_response_text = response.text.strip()
        if raw_response_text.startswith("```json"): raw_response_text = raw_response_text[7:]
        if raw_response_text.endswith("```"): raw_response_text = raw_response_text[:-3]
        raw_response_text = raw_response_text.strip()

        parsed_llm_output = json.loads(raw_response_text)
        intent_tool_name = parsed_llm_output.get("intent")
        extracted_params = parsed_llm_output.get("parameters", {})
        
        print(f"DEBUG [gemini_recognizer]: LLM selected tool='{intent_tool_name}', params={json.dumps(extracted_params)}")

        if not intent_tool_name: return "unknown", {"reason": "LLM did not specify an intent/tool."}
        if intent_tool_name == "unknown": return "unknown", extracted_params 

        chosen_tool_def = next((t for t in available_tools if t.get("name") == intent_tool_name), None)
        if not chosen_tool_def:
            return "unknown", {"reason": f"LLM chose a non-existent tool: '{intent_tool_name}'. Available tools: {[t.get('name') for t in available_tools]}"}

        missing_required_params = []
        tool_param_schema = chosen_tool_def.get("parameters", {})
        required_params_list = tool_param_schema.get("required", [])
        
        for req_param in required_params_list:
            if req_param not in extracted_params or extracted_params[req_param] is None or extracted_params[req_param] == "":
                param_prop_details = tool_param_schema.get("properties", {}).get(req_param, {})
                if "default" not in param_prop_details: 
                    missing_required_params.append(req_param)
        
        if missing_required_params:
            return "unknown", {"reason": f"LLM did not extract required parameters for tool '{intent_tool_name}': {', '.join(missing_required_params)}."}
        return intent_tool_name, extracted_params
    except json.JSONDecodeError as e:
        print(f"Failed to parse Gemini JSON (tool mode): {e}. Raw: {raw_response_text}")
        return "unknown", {"reason": f"LLM response (tool mode) was not valid JSON: {raw_response_text}"}
    except Exception as e:
        traceback.print_exc()
        return "unknown", {"reason": f"Error in Gemini tool recognition: {str(e)}"}
