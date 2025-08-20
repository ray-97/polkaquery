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

def execute_assethub_rpc_query(
    substrate_client: SubstrateInterface, 
    tool_definition: dict, 
    params: dict
) -> dict:
    """
    Executes a storage query using a provided Substrate client instance and tool definition.

    Args:
        substrate_client: An active and initialized SubstrateInterface instance.
        tool_definition: The dictionary containing the tool definition.
        params: A dictionary of parameters extracted by the LLM.

    Returns:
        A dictionary containing the query result or an error message.
    """
    if not substrate_client:
        print("ERROR [execute_assethub_rpc_query]: Substrate client is not provided or initialized.")
        return {"error": "Substrate client is not available."}

    intent_tool_name = tool_definition.get("name", "unnamed_tool")

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
            pallet_name,
            storage_item_name,
            ordered_params
        )
        
        # The result object has a .value attribute containing the data.
        return result.value

    except Exception as e:
        print(f"ERROR [execute_assethub_rpc_query]: Failed to execute query {pallet_name}.{storage_item_name}. Error: {e}")
        traceback.print_exc()
        return {"error": str(e)}

