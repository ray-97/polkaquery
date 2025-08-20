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

import asyncio
import traceback
from substrateinterface import SubstrateInterface

from polkaquery.providers.base import BaseToolProvider
from polkaquery.config import Settings

class AssetHubToolProvider(BaseToolProvider):
    """Generates tool definitions by connecting to an AssetHub node and reading its metadata."""
    def __init__(self, settings: Settings):
        super().__init__(settings, cache_subdirectory="assethub")

    def _map_substrate_type_to_json_schema(self, substrate_type_info: any) -> str:
        substrate_type_str = str(substrate_type_info[0] if isinstance(substrate_type_info, tuple) else substrate_type_info).lower()
        if any(t in substrate_type_str for t in ["u8", "u16", "u32", "u64", "u128", "compact"]):
            return "integer"
        if "bool" in substrate_type_str:
            return "boolean"
        return "string"

    def _generate_tools_sync(self) -> dict[str, dict]:
        """The synchronous implementation of tool generation."""
        tools = {}
        substrate = None
        ws_url = self.settings.assethub_ws_url
        if self.settings.onfinality_api_key:
            ws_url = f"{ws_url}?apikey={self.settings.onfinality_api_key}"
        
        print(f"INFO [AssetHubToolProvider]: Connecting to node at: {ws_url}")
        try:
            substrate = SubstrateInterface(url=ws_url)
            substrate.init_runtime()
            print(f"INFO [AssetHubToolProvider]: Connected to {substrate.chain} (runtime v{substrate.runtime_version})")

            for pallet in substrate.metadata.pallets:
                if not pallet.storage: continue
                for storage_item in pallet.storage:
                    if storage_item.name == ":__STORAGE_VERSION__:": continue

                    tool_name = f"{pallet.name.lower()}_{storage_item.name.lower()}"
                    parameters_schema = {"type": "object", "properties": {}, "required": []}
                    param_types = []
                    try:
                        param_types = storage_item.get_param_info()
                    except NotImplementedError:
                        pass
                    
                    for idx, p_type in enumerate(param_types):
                        param_name = f"key{idx+1}"
                        parameters_schema["properties"][param_name] = {
                            "type": self._map_substrate_type_to_json_schema(p_type),
                            "description": f"Parameter of type {p_type}"
                        }
                        parameters_schema["required"] .append(param_name)

                    tool_definition = {
                        "name": tool_name,
                        "description": ' '.join(storage_item.docs).strip() or f"Query the '{storage_item.name}' item from the '{pallet.name}' pallet.",
                        "client_type": "rpc",
                        "pallet_name": pallet.name,
                        "storage_item_name": storage_item.name,
                        "parameters": parameters_schema
                    }
                    tools[tool_name] = tool_definition
            return tools
        except Exception as e:
            print(f"ERROR [AssetHubToolProvider]: An error occurred during tool generation: {e}")
            traceback.print_exc()
            return {}
        finally:
            if substrate: substrate.close()

    async def _generate_tools(self) -> dict[str, dict]:
        """Runs the synchronous tool generation in a separate thread."""
        print("INFO [AssetHubToolProvider]: Running synchronous tool generation in a thread pool.")
        return await asyncio.to_thread(self._generate_tools_sync)
