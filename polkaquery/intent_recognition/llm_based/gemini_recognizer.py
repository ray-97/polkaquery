# Polkaquery
# Copyright (C) 2024 YOUR_NAME_OR_ORGANIZATION_NAME
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
import pathlib # For path manipulation
import glob # For finding all .json files in a directory

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("Warning: GOOGLE_API_KEY not found for gemini_recognizer. LLM queries might fail.")

# --- Load Tool Definitions from individual JSON files ---
AVAILABLE_TOOLS = []
# Path to the directory containing individual tool JSON files.
# This assumes gemini_recognizer.py is in polkaquery/intent_recognition/llm_based/
# and polkaquery_tool_definitions/ is in the project root.
TOOLS_DIR_PATH = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "polkaquery_tool_definitions"

if TOOLS_DIR_PATH.is_dir():
    for tool_file_path in glob.glob(str(TOOLS_DIR_PATH / "*.json")):
        try:
            with open(tool_file_path, 'r') as f:
                tool_definition = json.load(f)
                AVAILABLE_TOOLS.append(tool_definition)
            # print(f"DEBUG: Loaded tool '{tool_definition.get('name')}' from {tool_file_path}")
        except json.JSONDecodeError:
            print(f"Warning: Error decoding JSON from tool file: {tool_file_path}")
        except Exception as e:
            print(f"Warning: Error loading tool file {tool_file_path}: {e}")
    print(f"Successfully loaded {len(AVAILABLE_TOOLS)} tools from directory: {TOOLS_DIR_PATH}")
else:
    print(f"Warning: Tools directory not found at {TOOLS_DIR_PATH}. LLM tool selection will be empty.")
# --- End Load Tool Definitions ---

async def recognize_intent_with_gemini_llm(query: str, network_name: str) -> tuple[str, dict]:
    """
    Uses Google Gemini with tool definitions (loaded from multiple JSON files)
    to select a tool and extract parameters.
    """
    # print(f"DEBUG: Gemini LLM (Tool Mode) for query: '{query}' on network: '{network_name}'")
    # print(f"DEBUG: Number of available tools for LLM: {len(AVAILABLE_TOOLS)}")


    if not GOOGLE_API_KEY:
        return "unknown", {"reason": "Google API Key not configured."}
    if not AVAILABLE_TOOLS:
        return "unknown", {"reason": "No API tools loaded for LLM to use."}

    model = genai.GenerativeModel('gemini-1.5-flash')
    
    tools_prompt_section = "AVAILABLE TOOLS (CHOOSE ONE):\n"
    if not AVAILABLE_TOOLS:
        tools_prompt_section += "No tools available.\n"
    for tool in AVAILABLE_TOOLS:
        tools_prompt_section += f"- Name: {tool.get('name', 'Unnamed Tool')}\n"
        tools_prompt_section += f"  Description: {tool.get('description', 'No description.')}\n"
        # Only include parameters if they exist and are not empty
        if tool.get('parameters') and tool['parameters'].get('properties'):
            tools_prompt_section += f"  Parameters Schema: {json.dumps(tool['parameters'])}\n\n"
        else:
            tools_prompt_section += "  Parameters Schema: {}\n\n"


    prompt = f"""
    You are an expert AI assistant for the Polkaquery system, specializing in the Polkadot ecosystem.
    Your task is to understand user queries about the '{network_name}' network, select the most appropriate single tool
    from the list of AVAILABLE TOOLS, and extract the parameters required by that tool from the user's query.

    {tools_prompt_section}

    User Query: "{query}"
    Target Network: "{network_name}"

    Instructions:
    1. Analyze the User Query and the Target Network.
    2. Choose the single best tool from the AVAILABLE TOOLS that can fulfill the user's request.
    3. Extract all necessary parameters for the chosen tool from the User Query. Adhere strictly to the parameter types and requirements defined in the tool's Parameters Schema. If a parameter has a default value and is not specified in the query, you may omit it or use the default. Ensure all 'required' parameters are present.
    4. If no suitable tool is found, or if required parameters are missing for the best-fit tool (and they are not optional with defaults),
       respond with "intent": "unknown" and a "reason" in "parameters".
    5. Respond ONLY with a single, valid JSON object containing "intent" (which is the chosen tool's 'name')
       and "parameters" (an object with extracted parameter values).

    Example of a valid JSON response if a tool is chosen:
    {{"intent": "chosen_tool_name", "parameters": {{"param1_name": "value1", "param2_name": "value2"}}}}

    Example of a valid JSON response if no tool is suitable or parameters are missing:
    {{"intent": "unknown", "parameters": {{"reason": "Could not find a suitable tool or required parameters are missing."}}}}

    JSON Response:
    """

    try:
        generation_config = genai.types.GenerationConfig(
            temperature=0.0 # Low temperature for deterministic tool selection
        )
        # print(f"DEBUG: Prompt being sent to Gemini (length: {len(prompt)}):\n{prompt[:1000]}...") # For debugging
        
        response = await model.generate_content_async(prompt, generation_config=generation_config)

        raw_response_text = response.text.strip()
        if raw_response_text.startswith("```json"):
            raw_response_text = raw_response_text[7:]
        if raw_response_text.endswith("```"):
            raw_response_text = raw_response_text[:-3]
        raw_response_text = raw_response_text.strip()

        # print(f"DEBUG: Gemini Raw Tool Response Text: {raw_response_text}")
        parsed_llm_output = json.loads(raw_response_text)
        
        intent_tool_name = parsed_llm_output.get("intent")
        extracted_params = parsed_llm_output.get("parameters", {})

        if not intent_tool_name:
            return "unknown", {"reason": "LLM did not specify an intent/tool."}

        if intent_tool_name == "unknown":
            return "unknown", extracted_params 

        chosen_tool_def = next((t for t in AVAILABLE_TOOLS if t.get("name") == intent_tool_name), None)
        if not chosen_tool_def:
            return "unknown", {"reason": f"LLM chose a non-existent tool: '{intent_tool_name}'. Available tools: {[t.get('name') for t in AVAILABLE_TOOLS]}"}

        missing_required_params = []
        tool_param_schema = chosen_tool_def.get("parameters", {})
        required_params_list = tool_param_schema.get("required", [])
        
        for req_param in required_params_list:
            if req_param not in extracted_params or extracted_params[req_param] is None or extracted_params[req_param] == "":
                # Check if the parameter has a default defined in its property schema
                param_prop_details = tool_param_schema.get("properties", {}).get(req_param, {})
                if "default" not in param_prop_details: # If no default, it's truly missing
                    missing_required_params.append(req_param)
        
        if missing_required_params:
            return "unknown", {"reason": f"LLM did not extract required parameters for tool '{intent_tool_name}': {', '.join(missing_required_params)}."}

        return intent_tool_name, extracted_params

    except json.JSONDecodeError as e:
        print(f"Failed to parse Gemini JSON (tool mode): {e}. Raw: {raw_response_text}")
        return "unknown", {"reason": f"LLM response (tool mode) was not valid JSON: {raw_response_text}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return "unknown", {"reason": f"Error in Gemini tool recognition: {str(e)}"}

