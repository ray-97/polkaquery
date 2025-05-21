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

import httpx # For calling Polkaquery API and Ollama API
import json
import os
import traceback

# Configuration
POLKAQUERY_API_URL = "http://127.0.0.1:8000/llm-query/" # Your Polkaquery FastAPI endpoint
OLLAMA_API_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/chat" 

# Ensure we are using phi3:mini for this specific request
OLLAMA_MODEL = "phi3:mini" 
# You can also allow overriding via environment variable:
# OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini") 


# --- Helper function to call Polkaquery API ---
async def call_polkaquery(query: str, network: str = "polkadot") -> dict | None:
    payload = {"query": query, "network": network}
    print(f"\nCalling Polkaquery API with: {payload}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(POLKAQUERY_API_URL, json=payload, timeout=60.0)
            response.raise_for_status()
            result = response.json()
            print(f"Polkaquery API Response: {result}")
            return result
    except Exception as e:
        print(f"Error calling Polkaquery API: {e}")
        return None

# --- Helper function to call Ollama LLM using /api/chat ---
async def call_ollama_llm(system_prompt: str, user_prompt: str, model: str = OLLAMA_MODEL) -> str | None:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    
    payload = {
        "model": model, # Uses the OLLAMA_MODEL defined above
        "messages": messages,
        "stream": False, 
        "format": "json" 
    }
    print(f"\nCalling Ollama LLM (model: {model}) with user prompt (first 200 chars): {user_prompt[:200]}...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OLLAMA_API_URL, json=payload, timeout=120.0) 
            response.raise_for_status()
            
            ollama_json_response = response.json()
            message_content_str = ollama_json_response.get("message", {}).get("content")
            
            if message_content_str:
                return message_content_str 
            else:
                print(f"Error: 'message.content' field missing or empty in Ollama's JSON output. Full response: {ollama_json_response}")
                return None

    except httpx.HTTPStatusError as e:
        print(f"Error calling Ollama LLM (HTTP Status {e.response.status_code}): {e.response.text}")
        return None
    except Exception as e:
        print(f"Error calling Ollama LLM: {e}")
        traceback.print_exc()
        return None

async def run_ollama_polkaquery_interaction(user_query: str, network: str = "polkadot"):
    print(f"\n--- Starting Ollama Interaction for Query: '{user_query}' on Network: '{network}' ---")

    system_prompt_for_decision = """
    You are an AI assistant. Your task is to decide if a specialized tool called "Polkaquery" should be used.
    Polkaquery can answer questions about the Polkadot ecosystem (balances, extrinsics, blocks, staking, governance, assets, and general Polkadot info via internet search).
    If Polkaquery is appropriate, formulate the question for it. If not, explain why.
    Respond ONLY with a JSON object with two keys: "use_polkaquery" (boolean) and "polkaquery_question" (string).
    Example for using Polkaquery: {"use_polkaquery": true, "polkaquery_question": "What is the balance of the Polkadot Treasury account?"}
    Example for not using Polkaquery (if query was "What is the weather?"): {"use_polkaquery": false, "polkaquery_question": "Polkaquery is for Polkadot ecosystem questions, not general weather."}
    """
    user_prompt_for_decision = f"The user has asked: \"{user_query}\" for the {network} network. Based on this, provide your JSON decision."

    llm_decision_str = await call_ollama_llm(system_prompt_for_decision, user_prompt_for_decision)
    if not llm_decision_str:
        print("Failed to get a decision from Ollama.")
        return

    try:
        decision = json.loads(llm_decision_str)
    except json.JSONDecodeError as e:
        print(f"Failed to parse LLM decision JSON. Error: {e}. Raw string: {llm_decision_str}")
        return

    print(f"LLM Decision: {decision}")

    if decision.get("use_polkaquery"):
        polkaquery_q = decision.get("polkaquery_question", user_query) 
        
        polkaquery_result = await call_polkaquery(query=polkaquery_q, network=network)
        
        if polkaquery_result and "answer" in polkaquery_result:
            print("\n--- Final Answer (from Polkaquery via Ollama workflow) ---")
            print(polkaquery_result["answer"])
        else:
            print("Polkaquery did not return a valid answer.")
            system_prompt_on_failure = "You are an AI assistant."
            user_prompt_on_failure = f"""
            The user's original query was: "{user_query}" for the {network} network.
            I tried to use Polkaquery with the question "{polkaquery_q}", but it failed or returned no answer.
            Please provide a polite response to the user indicating the information could not be retrieved.
            Respond ONLY with the user-facing message as a JSON object like: {{"response": "Your message here."}}
            """
            final_response_str = await call_ollama_llm(system_prompt_on_failure, user_prompt_on_failure)
            if final_response_str:
                try:
                    final_response_json = json.loads(final_response_str)
                    print("\n--- Final Answer (Ollama generated on Polkaquery failure) ---")
                    print(final_response_json.get("response", "Could not retrieve the information at this time."))
                except json.JSONDecodeError:
                    print("\n--- Final Answer (Ollama generated on Polkaquery failure, but not valid JSON) ---")
                    print(final_response_str) 
            else:
                print("\nCould not retrieve the information at this time (Ollama also failed to generate a fallback).")
    else:
        print("\n--- Final Answer (Ollama decided not to use Polkaquery) ---")
        print(decision.get("polkaquery_question", "LLM decided Polkaquery was not needed, but gave no specific explanation."))

async def main():
    print(f"Using Ollama model: {OLLAMA_MODEL}") # This will now reflect "phi3:mini"
    queries_to_test = [
        ("What is the balance of 13Z7KjGnzdAdMre9cqRwTZHR6F2p36gqBsaNmQwwosiPz8JT as of block 26100918?", "polkadot"),
        ("Tell me about Polkadot 2.0.", "polkadot"),
        ("What is the weather like in Berlin?", "polkadot") 
    ]
    for query, network in queries_to_test:
        await run_ollama_polkaquery_interaction(user_query=query, network=network)
        print("-" * 70)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
