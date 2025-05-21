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
from dotenv import load_dotenv
import traceback
import json
from typing import Optional 
import re

# --- Load environment variables FIRST ---
# print("Attempting to load environment variables from .env file...") # DEBUG
dotenv_path = load_dotenv() 
if dotenv_path:
    # print(f".env file loaded successfully from: {dotenv_path if isinstance(dotenv_path, str) else 'current directory (or parent)'}") # DEBUG
    pass
else:
    print("Warning: .env file not found or not loaded by load_dotenv(). Ensure it's in the same directory as this script or the project root from where you run it.")

# --- DEBUG: Print all environment variables ---
# print("\n--- All Environment Variables Visible to Script ---") # DEBUG
# for key, value in os.environ.items(): # DEBUG
#     if "KEY" in key.upper() or "TOKEN" in key.upper() or "SECRET" in key.upper(): # DEBUG
#         print(f"{key}=******{value[-4:] if len(value) > 4 else ''}") # DEBUG
#     elif len(value) > 100: # DEBUG
#         print(f"{key}={value[:50]}... (truncated)") # DEBUG
#     else: # DEBUG
#         print(f"{key}={value}") # DEBUG
# print("--- End of Environment Variables ---\n") # DEBUG
# --- END DEBUG ---


# --- Langchain Imports ---
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    print("Successfully imported ChatGoogleGenerativeAI from langchain_google_genai.")
except ImportError:
    print("CRITICAL: langchain_google_genai not found.")
    print("Please run 'pip install -U langchain-google-genai' to install it.")
    ChatGoogleGenerativeAI = None

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, ValidationError 
from langchain_core.output_parsers.json import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

# --- Custom Polkaquery Tool ---
from polkaquery_langchain_tool import PolkaqueryTool, POLKAQUERY_API_URL, PolkaqueryInput

GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY") 

class ToolCallDecision(BaseModel):
    tool_name: str = Field(description="The name of the tool to call. Should be 'polkaquery_search' or 'no_tool'.")
    tool_input: Optional[PolkaqueryInput] = Field(default=None, description="The input arguments for the PolkaqueryTool if 'tool_name' is 'polkaquery_search'.")
    reasoning: str = Field(description="Brief reasoning for the decision.")

def run_gemini_langchain_interaction():
    print("Initializing Langchain interaction with PolkaqueryTool using Google Gemini...")

    if not ChatGoogleGenerativeAI:
        print("ChatGoogleGenerativeAI class not available. Exiting.")
        return

    if not GOOGLE_GEMINI_API_KEY:
        print("Error: GOOGLE_GEMINI_API_KEY was not found in the script's environment variables after attempting to load .env.")
        print("Please ensure GOOGLE_GEMINI_API_KEY is set in your .env file or as an environment variable.")
        return

    GEMINI_MODEL_TO_USE = "gemini-1.5-flash-latest" 
    
    try:
        llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL_TO_USE,
            temperature=0,
            google_api_key=GOOGLE_GEMINI_API_KEY 
        )
        print(f"Using ChatGoogleGenerativeAI with model '{GEMINI_MODEL_TO_USE}' and explicit API key.")
    except Exception as e:
        print(f"Failed to initialize ChatGoogleGenerativeAI with model '{GEMINI_MODEL_TO_USE}': {e}")
        traceback.print_exc()
        return

    polkaquery_tool = PolkaqueryTool()
    tool_args_schema_static = json.dumps(polkaquery_tool.args_schema.model_json_schema(), indent=2)

    prompt_template_str = """
    You are an AI assistant. Your task is to decide if "PolkaqueryTool" should be used for the User Question about the Polkadot ecosystem.
    You MUST respond with a valid JSON object that conforms to the specified schema, and nothing else. Do not add any explanatory text before or after the JSON object.

    PolkaqueryTool Details:
    Name: {tool_name_static}
    Description: {tool_description_static}
    Input Schema: {tool_args_schema_static} 

    User Question: "{user_question}"
    Target Network (if specified by user, otherwise default to 'polkadot'): "{network_context}"

    Decision Process:
    1. If PolkaqueryTool can answer the User Question, set "tool_name" to "{tool_name_static}" and provide "tool_input" (query, optional network).
    2. Otherwise, set "tool_name" to "no_tool".
    3. Provide brief "reasoning".

    Respond ONLY with a single, valid JSON object matching the following schema:
    {{
        "tool_name": "string (either '{tool_name_static}' or 'no_tool')",
        "tool_input": {{ "query": "string (the question for PolkaqueryTool)", "network": "string (e.g., 'polkadot', 'kusama', optional)" }} (This field should be null or omitted if tool_name is 'no_tool'),
        "reasoning": "string (your brief reasoning)"
    }}
    """
    
    base_prompt = ChatPromptTemplate.from_template(prompt_template_str)
    prompt = base_prompt.partial(
        tool_name_static=polkaquery_tool.name,
        tool_description_static=polkaquery_tool.description,
        tool_args_schema_static=tool_args_schema_static
    )

    output_parser = JsonOutputParser(pydantic_object=ToolCallDecision)
    
    def debug_llm_input(prompt_value):
        # print("\n--- DEBUG: Formatted Prompt to Gemini LLM ---") # DEBUG
        # if hasattr(prompt_value, 'to_string'): print(prompt_value.to_string()) # DEBUG
        # elif hasattr(prompt_value, 'to_messages'): # DEBUG
        #     for msg in prompt_value.to_messages(): print(f"Type: {type(msg).__name__}, Content: {msg.content}") # DEBUG
        # else: print(prompt_value) # DEBUG
        # print("--- END DEBUG: Formatted Prompt to Gemini LLM ---\n") # DEBUG
        return prompt_value 

    def debug_llm_output(llm_result):
        # print("\n--- DEBUG: Raw LLM Output (before JSON parsing) ---") # DEBUG
        content_from_llm = ""
        if hasattr(llm_result, 'content') and isinstance(llm_result.content, str): 
            # print(f"Type: {type(llm_result)}, Content: {llm_result.content}") # DEBUG
            content_from_llm = llm_result.content 
        else: 
            # print(f"Type: {type(llm_result)}, Value: {llm_result} (Unexpected format from LLM)") # DEBUG
            content_from_llm = str(llm_result)
        
        if isinstance(content_from_llm, str): 
            match = re.search(r"\{.*\}", content_from_llm, re.DOTALL) 
            if match:
                content_from_llm = match.group(0) 
        # print(f"Content to be parsed by JsonOutputParser: {content_from_llm}") # DEBUG
        return content_from_llm 

    chain = (
        prompt 
        | RunnableLambda(debug_llm_input) 
        | llm 
        | RunnableLambda(debug_llm_output) 
        | output_parser
    )
    print("Langchain chain initialized with Google Gemini.") # Removed "and debug steps"

    queries_with_network = [
        ("What is the balance of 13Z7KjGnzdAdMre9cqRwTZHR6F2p36gqBsaNmQwwosiPz8JT as of block 26100918?", "polkadot"),
        ("What is Polkadot 2.0 about?", "polkadot"),
    ]

    for q, net in queries_with_network:
        print(f"\n--- Processing Query: '{q}' for network '{net}' ---")
        try:
            # print(f"DEBUG: About to call chain.invoke for query: '{q}'...") # DEBUG
            llm_decision_output = chain.invoke({ 
                "user_question": q,
                "network_context": net
            })
            # print(f"DEBUG: chain.invoke completed for query: '{q}'.") # DEBUG
            # print(f"DEBUG: Type of llm_decision_output from chain: {type(llm_decision_output)}") # DEBUG
            # print(f"DEBUG: Value of llm_decision_output from chain: {llm_decision_output}") # DEBUG

            llm_decision: ToolCallDecision
            if isinstance(llm_decision_output, dict):
                # print("DEBUG: llm_decision_output is a dict, attempting to cast to ToolCallDecision.") # DEBUG
                try:
                    if llm_decision_output.get("tool_input") is None and "tool_input" in ToolCallDecision.model_fields:
                         pass
                    llm_decision = ToolCallDecision(**llm_decision_output)
                except ValidationError as pydantic_exc:
                    # print(f"DEBUG: Failed to cast dict to ToolCallDecision: {pydantic_exc}") # DEBUG
                    # print(f"DEBUG: Dictionary that failed casting: {llm_decision_output}") # DEBUG
                    raise 
            elif isinstance(llm_decision_output, ToolCallDecision):
                llm_decision = llm_decision_output
            else:
                # print(f"DEBUG: Unexpected type for llm_decision_output: {type(llm_decision_output)}") # DEBUG
                raise TypeError(f"Expected ToolCallDecision or dict, got {type(llm_decision_output)}")
            
            print(f"LLM Decision (Pydantic object): tool_name='{llm_decision.tool_name}', input='{llm_decision.tool_input}', reasoning='{llm_decision.reasoning}'")

            if llm_decision.tool_name == polkaquery_tool.name and llm_decision.tool_input:
                print(f"LLM decided to use PolkaqueryTool. Calling tool...")
                tool_run_input = llm_decision.tool_input.model_dump() 
                tool_response = polkaquery_tool.run(tool_run_input) 
                print(f"\nFinal Answer (from PolkaqueryTool for '{q}'):")
                print(tool_response)
            elif llm_decision.tool_name == "no_tool":
                print(f"\nFinal Answer (LLM decided not to use Polkaquery for '{q}'):")
                print(f"LLM Reasoning: {llm_decision.reasoning}. I cannot answer this with Polkaquery.")
            else:
                print(f"\nWarning: LLM returned an unexpected tool_name in JSON: {llm_decision.tool_name}")

        except Exception as e:
            print(f"Error processing query '{q}': {e}")
            print("This could be due to the LLM not returning valid JSON, a timeout, an issue with the tool itself, or an authentication/permission problem with the Google API.")
            traceback.print_exc()

    print("\n--- Langchain Gemini Interaction Finished ---")
    print(f"Ensure your Polkaquery FastAPI server is running at {POLKAQUERY_API_URL}")

if __name__ == "__main__":
    run_gemini_langchain_interaction()
