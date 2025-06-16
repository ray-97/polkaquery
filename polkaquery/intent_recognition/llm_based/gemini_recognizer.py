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
import json
import google.generativeai as genai
from dotenv import load_dotenv
import pathlib 
import glob 
import traceback

load_dotenv()
GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")

if GOOGLE_GEMINI_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
    except Exception as e:
        print(f"Error configuring Gemini API in gemini_recognizer.py: {e}")
else:
    print("Warning: GOOGLE_GEMINI_API_KEY not found for gemini_recognizer. LLM queries might fail.")

AVAILABLE_SUBSCAN_TOOLS = []
AVAILABLE_ASSETHUB_TOOLS = []

TOOLS_DIR_PATH_SUBSCAN = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "polkaquery_tool_definitions" / "subscan"
TOOLS_DIR_PATH_ASSETHUB = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "polkaquery_tool_definitions" / "assethub"

# Load Subscan tools
if TOOLS_DIR_PATH_SUBSCAN.is_dir():
    for tool_file_path in glob.glob(str(TOOLS_DIR_PATH_SUBSCAN / "*.json")):
        try:
            with open(tool_file_path, 'r') as f:
                tool_definition = json.load(f)
                AVAILABLE_SUBSCAN_TOOLS.append(tool_definition)
        except Exception as e:
            print(f"Warning: Error loading tool file {tool_file_path}: {e}")
    print(f"Gemini Recognizer: Loaded {len(AVAILABLE_SUBSCAN_TOOLS)} Subscan tools from: {TOOLS_DIR_PATH_SUBSCAN}")
else:
    print(f"Warning: Subscan tools directory not found at {TOOLS_DIR_PATH_SUBSCAN}.")

# Load AssetHub tools


# Define and add the Internet Search tool
INTERNET_SEARCH_TOOL = {
  "name": "internet_search",
  "description": "Performs a general internet search to find information when the user's query is broad, asks for general knowledge, explanations, news, or topics not covered by specific blockchain data APIs (like Subscan tools). Use this if no specific Subscan tool directly matches the query's intent for on-chain data.",
  "api_path": None, # Not a Subscan API
  "api_method": None, # Not a Subscan API
  "parameters": {
    "type": "object",
    "properties": {
      "search_query": {
        "type": "string",
        "description": "A concise and effective search query derived from the user's original question, suitable for a web search engine."
      }
    },
    "required": ["search_query"]
  },
  "response_schema_description": "Returns a text summary of relevant information found on the internet."
}
AVAILABLE_SUBSCAN_TOOLS.append(INTERNET_SEARCH_TOOL)
AVAILABLE_ASSETHUB_TOOLS.append(INTERNET_SEARCH_TOOL)

def llm_instruction_by_network(network_name: str) -> str:
    if network_name == "assethub-polkadot-rpc":
        pass
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
    
def select_available_tools_by_network(network_name: str) -> list:
    if network_name == "assethub-polkadot-rpc":
        return AVAILABLE_ASSETHUB_TOOLS
    else:
        return AVAILABLE_SUBSCAN_TOOLS

async def recognize_intent_with_gemini_llm(query: str, network_name: str) -> tuple[str, dict]:
    if not GOOGLE_GEMINI_API_KEY:
        return "unknown", {"reason": "Google Gemini API Key not configured."}
    if not AVAILABLE_SUBSCAN_TOOLS: # Should at least have internet_search
        return "unknown", {"reason": "No API tools (including internet search) loaded for LLM to use."}
    if not AVAILABLE_ASSETHUB_TOOLS:
        return "unknown", {"reason": "No AssetHub API tools (including internet search) loaded for LLM to use."}

    model = genai.GenerativeModel('gemini-1.5-flash')
    
    instructions = llm_instruction_by_network(network_name)

    tools_prompt_section = "AVAILABLE TOOLS (CHOOSE ONE):\n"
    for tool in select_available_tools_by_network(network_name):
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

        chosen_tool_def = next((t for t in AVAILABLE_SUBSCAN_TOOLS if t.get("name") == intent_tool_name), None)
        if not chosen_tool_def:
            return "unknown", {"reason": f"LLM chose a non-existent tool: '{intent_tool_name}'. Available tools: {[t.get('name') for t in AVAILABLE_SUBSCAN_TOOLS]}"}

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
