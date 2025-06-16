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

# Connects to an AssetHub node, fetches its runtime metadata,
# and generates JSON tool definitions for all available storage queries.
# These definitions are structured for use with an RPC client.

import os
import json
import ssl
from substrateinterface import SubstrateInterface
from substrateinterface.base import StorageKey
import pprint

# --- Configuration ---
# The WebSocket URL of the node to connect to.
ASSET_HUB_WS_URL = "wss://statemint.api.onfinality.io/public-ws"
# The directory where the generated JSON tool files will be saved.
OUTPUT_DIRECTORY = "polkaquery_tool_definitions/assethub"

def map_substrate_type_to_json_schema(substrate_type_str: str) -> str:
    """
    A simple mapping from Substrate types to JSON Schema types.
    Can be expanded as needed.
    """
    substrate_type_str = substrate_type_str.lower()
    if 'u8' in substrate_type_str or 'u16' in substrate_type_str or \
       'u32' in substrate_type_str or 'u64' in substrate_type_str or \
       'u128' in substrate_type_str or 'compact' in substrate_type_str:
        return "integer"
    if 'bool' in substrate_type_str:
        return "boolean"
    # Default to string for complex types like AccountId32, H256, etc.
    return "string"

def generate_rpc_tools(ws_url: str, output_dir: str):
    """
    Connects to a node, scrapes the runtime, and generates JSON tool
    definitions for storage queries.
    """
    print(f"--- Starting AssetHub RPC Tool Generator ---")
    print(f"Connecting to node at: {ws_url}")
    
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    print(f"Tool definitions will be saved in: {output_dir}")
    
    substrate = None
    try:
        # Connect to the node. The library handles fetching the metadata.
        substrate = SubstrateInterface(
            url=ws_url
        )
        # Explicitly initialize the runtime to fetch metadata
        substrate.init_runtime()
        
        print(f"Successfully connected to {substrate.chain} (runtime v{substrate.runtime_version})")
        print("-" * 50)
        
        # Iterate through each pallet in the runtime metadata
        for i, pallet in enumerate(substrate.metadata.pallets):
            if pallet.storage:
                
                # Let's inspect the 'Assets' pallet specifically as it has maps
                if pallet.name == 'Assets':
                    print(f"\nFound pallet with storage: {pallet.name}")
                    # Loop through all storage items in the 'Assets' pallet
                    for storage_item in pallet.storage:
                        # --- DEBUGGING: Exploring the promising methods ---
                        print(f"\n[DEBUG] Inspecting storage item: {pallet.name}.{storage_item.name}")
                        
                        try:
                            print(f"\n--> Exploring 'get_param_hashers()':")
                            pprint.pprint(storage_item.get_param_hashers())
                        except Exception as e:
                            print(f"    Error calling get_param_hashers(): {e}")
                            
                        try:
                            print(f"\n--> Exploring 'get_param_info()':")
                            pprint.pprint(storage_item.get_param_info())
                        except Exception as e:
                            print(f"    Error calling get_param_info(): {e}")
                            
                        try:
                            print(f"\n--> Exploring 'get_params_type_string()':")
                            pprint.pprint(storage_item.get_params_type_string())
                        except Exception as e:
                            print(f"    Error calling get_params_type_string(): {e}")

                        print("-" * 50)
                    
                    # Stop after inspecting the Assets pallet
                    print("[INFO] Script finished after inspecting all items in the 'Assets' pallet.")
                    return

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if substrate and substrate.websocket:
            substrate.close()
            print("\nConnection closed.")

if __name__ == "__main__":
    generate_rpc_tools(ASSET_HUB_WS_URL, OUTPUT_DIRECTORY)
