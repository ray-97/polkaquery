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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
This module provides a function for executing queries on an AssetHub node
using a pre-initialized SubstrateInterface client.
"""
from substrateinterface import SubstrateInterface
import traceback
import json
import pathlib

# Define the base path to the RPC tool definitions directory
TOOLS_DIR_PATH = pathlib.Path(__file__).resolve().parent.parent / "polkaquery_tool_definitions" / "assethub"

def load_rpc_tool_definition(intent_tool_name: str) -> dict:
    """
    Loads the JSON tool definition for a given RPC tool name.

    Args:
        intent_tool_name: The name of the tool, corresponding to the JSON filename.

    Returns:
        A dictionary containing the tool definition.

    Raises:
        FileNotFoundError: If the tool definition JSON file cannot be found.
    """
    tool_file_path = TOOLS_DIR_PATH / f"{intent_tool_name}.json"
    if not tool_file_path.is_file():
        raise FileNotFoundError(f"RPC tool definition not found: {tool_file_path}")
    
    with open(tool_file_path, 'r') as f:
        return json.load(f)

def execute_assethub_rpc_query(substrate_client: SubstrateInterface, intent_tool_name: str, params: dict) -> dict:
    """
    Executes a storage query using a provided Substrate client instance by
    first loading the appropriate tool definition.

    Args:
        substrate_client: An active and initialized SubstrateInterface instance.
        intent_tool_name: The name of the tool to execute, corresponding to a JSON file.
        params: A dictionary of parameters extracted by the LLM.

    Returns:
        .A dictionary containing the query result or an error message
    """
    if not substrate_client:
        print("ERROR [execute_assethub_rpc_query]: Substrate client is not provided or initialized.")
        return {"error": "Substrate client is not available."}

    try:
        tool_definition = load_rpc_tool_definition(intent_tool_name)
    except FileNotFoundError as e:
        print(f"ERROR [execute_assethub_rpc_query]: {e}")
        return {"error": str(e)}

    pallet_name = tool_definition.get("pallet_name")
    storage_item_name = tool_definition.get("storage_item_name")

    if not pallet_name or not storage_item_name:
        return {"error": f"Invalid RPC tool definition for '{intent_tool_name}'; missing pallet or storage item name."}
    
    # Order the parameters correctly. The generator creates `key1`, `key2`, etc., in order.
    param_keys = sorted(tool_definition.get("parameters", {}).get("required", []))
    ordered_params = [params.get(key) for key in param_keys]

    try:
        print(f"INFO [execute_assethub_rpc_query]: Querying {pallet_name}.{storage_item_name} with params: {ordered_params}")
        
        result = substrate_client.query(
            pallet=pallet_name,
            storage_item=storage_item_name,
            params=ordered_params
        )
        
        # The result object has a .value attribute containing the data.
        return result.value

    except Exception as e:
        print(f"ERROR [execute_assethub_rpc_query]: Failed to execute query {pallet_name}.{storage_item_name}. Error: {e}")
        traceback.print_exc()
        return {"error": str(e)}

