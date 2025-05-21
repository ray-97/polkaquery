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

import httpx
import json
from typing import Type, Optional, Any
from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool
from langchain_core.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)

# Configuration for the Polkaquery API
POLKAQUERY_API_URL = "http://127.0.0.1:8000/llm-query/" # Ensure your Polkaquery FastAPI is running here

class PolkaqueryInput(BaseModel):
    query: str = Field(description="The natural language query to send to Polkaquery.")
    network: Optional[str] = Field(
        default="polkadot", 
        description="Optional. The Polkadot ecosystem network to target (e.g., 'polkadot', 'kusama', 'statemint'). Defaults to 'polkadot'."
    )

class PolkaqueryTool(BaseTool):
    """
    A tool for querying the Polkaquery service to get information about the Polkadot ecosystem.
    It uses the Polkaquery /llm-query/ endpoint which leverages an LLM for intent recognition,
    data retrieval via Subscan or internet search, and final answer synthesis.
    """
    name: str = "polkaquery_search"
    description: str = (
        "Useful for when you need to answer questions about the Polkadot ecosystem. "
        "This includes queries about account balances, extrinsic details, block information, "
        "staking, governance, specific assets on parachains like AssetHub (Statemint/Statemine), "
        "or general Polkadot-related news and explanations. "
        "Input should be a natural language query. You can also specify a network like 'kusama' or 'statemint'."
    )
    args_schema: Type[BaseModel] = PolkaqueryInput
    # return_direct: bool = False # Set to True if the tool's output should be the final answer directly

    def _run(
        self, query: str, network: Optional[str] = "polkadot", run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool synchronously."""
        payload = {"query": query, "network": network or "polkadot"}
        try:
            with httpx.Client() as client:
                response = client.post(POLKAQUERY_API_URL, json=payload, timeout=60.0) # Increased timeout
                response.raise_for_status() # Raise an exception for bad status codes
                result = response.json()
                # The Polkaquery API's /llm-query/ endpoint already returns a synthesized answer.
                return result.get("answer", "No answer found or error in Polkaquery response.")
        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            return f"Error calling Polkaquery API: {e.response.status_code} - {error_body}"
        except httpx.RequestError as e:
            return f"Request error calling Polkaquery API: {str(e)}"
        except json.JSONDecodeError:
            return "Error: Could not decode JSON response from Polkaquery API."
        except Exception as e:
            return f"An unexpected error occurred when using PolkaqueryTool: {str(e)}"

    async def _arun(
        self, query: str, network: Optional[str] = "polkadot", run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool asynchronously."""
        payload = {"query": query, "network": network or "polkadot"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(POLKAQUERY_API_URL, json=payload, timeout=60.0) # Increased timeout
                response.raise_for_status()
                result = response.json()
                return result.get("answer", "No answer found or error in Polkaquery response.")
        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            return f"Error calling Polkaquery API: {e.response.status_code} - {error_body}"
        except httpx.RequestError as e:
            return f"Request error calling Polkaquery API: {str(e)}"
        except json.JSONDecodeError:
            return "Error: Could not decode JSON response from Polkaquery API."
        except Exception as e:
            return f"An unexpected error occurred when using PolkaqueryTool: {str(e)}"

if __name__ == '__main__':
    # Example of using the tool directly (synchronously)
    # Make sure your Polkaquery FastAPI server is running at POLKAQUERY_API_URL
    tool = PolkaqueryTool()
    
    # Test Case 1: Balance query
    print("\n--- Test Case 1: Balance Query ---")
    result1 = tool.run({"query": "What is the balance of 13Z7KjGnzdAdMre9cqRwTZHR6F2p36gqBsaNmQwwosiPz8JT as of block 26100918?", "network": "polkadot"})
    print(f"Polkaquery Result 1: {result1}")

    # Test Case 2: Broad query (should use internet search via Polkaquery)
    print("\n--- Test Case 2: Broad Query ---")
    result2 = tool.run({"query": "What is Polkadot 2.0?"}) # Default network is polkadot
    print(f"Polkaquery Result 2: {result2}")

    # Test Case 3: Specific extrinsic on Kusama
    print("\n--- Test Case 3: Polkadot Extrinsic ---")
    # Find a recent extrinsic hash from kusama.subscan.io for testing
    polkadot_extrinsic_hash = "0x06ff94b4cd74702dc54b0d124415a3369113b762656c3efd246a6a59bfe66d89" # Replace with a real one
    result3 = tool.run({
        "query": f"Details for extrinsic {polkadot_extrinsic_hash} on Polkadot",
        "network": "polkadot"
    })
    print(f"Polkaquery Result 3: {result3}")

