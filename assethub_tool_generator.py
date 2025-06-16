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
#
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

def map_substrate_type_to_json_schema(substrate_type_info: any) -> str:
    """
    A simple mapping from Substrate types to JSON Schema types.
    Can be expanded as needed.
    """
    substrate_type_str = ""
    if isinstance(substrate_type_info, tuple) and len(substrate_type_info) > 0:
        substrate_type_str = str(substrate_type_info[0])
    elif isinstance(substrate_type_info, str):
        substrate_type_str = substrate_type_info
    else:
        # Fallback for unexpected types
        substrate_type_str = str(substrate_type_info)


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
        
        generated_files = 0
        skipped_files = 0
        total_pallets = len(substrate.metadata.pallets)
        print(f"Found {total_pallets} pallets to process...")

        # Iterate through each pallet in the runtime metadata
        for i, pallet in enumerate(substrate.metadata.pallets):
            if pallet.storage:
                total_storage_items = len(pallet.storage)
                print(f"\nProcessing pallet {i+1}/{total_pallets}: {pallet.name} ({total_storage_items} storage items)")

                for storage_item in pallet.storage:
                    # --- ADDED: Skip internal storage version items ---
                    if storage_item.name == ':__STORAGE_VERSION__:':
                        skipped_files += 1
                        continue

                    # --- Construct the Tool Name ---
                    tool_name = f"assethub_{pallet.name.lower()}_{storage_item.name.lower()}"
                    
                    # --- Construct the Parameters Schema ---
                    parameters_schema = {"type": "object", "properties": {}, "required": []}
                    
                    param_types = []
                    try:
                        param_types = storage_item.get_param_info()
                    except NotImplementedError:
                        pass
                    
                    param_names = [f"key{idx+1}" for idx, _ in enumerate(param_types)]

                    for name, p_type in zip(param_names, param_types):
                        parameters_schema["properties"][name] = {
                            "type": map_substrate_type_to_json_schema(p_type),
                            "description": f"Parameter of type {p_type}"
                        }
                        parameters_schema["required"].append(name)

                    # --- Assemble the RPC Tool Definition ---
                    docs = ' '.join(storage_item.docs).strip() or f"Query the '{storage_item.name}' item from the '{pallet.name}' pallet."
                    
                    tool_definition = {
                        "name": tool_name,
                        "description": docs,
                        "client_type": "rpc",
                        "pallet_name": pallet.name,
                        "storage_item_name": storage_item.name,
                        "parameters": parameters_schema
                    }
                    
                    # --- Save to a JSON file ---
                    file_path = os.path.join(output_dir, f"{tool_name}.json")
                    with open(file_path, 'w') as f:
                        json.dump(tool_definition, f, indent=4)
                    
                    generated_files += 1

        print(f"\n--- Generation Complete ---")
        print(f"Successfully generated {generated_files} RPC tool definition files in '{output_dir}'.")
        print(f"Skipped {skipped_files} internal storage version items.")

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