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
from polkaquery.core.async_cache import async_cached, llm_cache, llm_recognizer_caching_key

@async_cached(cache=llm_cache, key=llm_recognizer_caching_key)
async def recognize_intent_with_gemini_llm(
    query: str, 
    model: genai.GenerativeModel, 
    available_tools: list[dict],
    prompt_template: str
) -> tuple[str, dict]:
    if not model:
        return "unknown", {"reason": "Google Gemini model is not available."}
    if not available_tools:
        return "unknown", {"reason": "No API tools loaded for LLM to use."}
    if not prompt_template:
        return "unknown", {"reason": "Prompt template not provided."}

    tools_prompt_section = "AVAILABLE TOOLS (CHOOSE ONE):\n"
    for tool in available_tools:
        tools_prompt_section += f"- Name: {tool.get('name', 'Unnamed Tool')}\n"
        tools_prompt_section += f"  Description: {tool.get('description', 'No description.')}\n"
        if tool.get('parameters') and tool['parameters'].get('properties'):
            tools_prompt_section += f"  Parameters Schema: {json.dumps(tool['parameters'])}\n\n"
        else:
            tools_prompt_section += "  Parameters Schema: {}\n\n"

    prompt = f"""
    {prompt_template}

    {tools_prompt_section}

    User Query: \"{query}\"\n
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