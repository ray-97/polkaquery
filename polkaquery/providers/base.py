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
import glob
import pathlib
import re
from abc import ABC, abstractmethod

from polkaquery.config import Settings

class BaseToolProvider(ABC):
    """
    Abstract base class for a provider that can generate and cache tool definitions.
    """
    def __init__(self, settings: Settings, cache_subdirectory: str):
        self.settings = settings
        self.cache_dir = pathlib.Path(settings.tools_output_directory) / cache_subdirectory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    async def _generate_tools(self) -> dict[str, dict]:
        """The core logic for generating tools from the source."""
        pass

    def _load_from_cache(self) -> dict[str, dict]:
        """Loads all tool definitions from the provider's cache directory."""
        tools = {}
        if not self.cache_dir.is_dir():
            return tools

        for tool_file in glob.glob(str(self.cache_dir / "*.json")):
            try:
                with open(tool_file, 'r') as f:
                    tool_def = json.load(f)
                    if tool_def.get("name"):
                        tools[tool_def["name"]] = tool_def
            except Exception as e:
                print(f"WARN [BaseToolProvider]: Failed to load cached tool {tool_file}: {e}")
        return tools

    def _save_to_cache(self, tools: dict[str, dict]):
        """Saves the provided tool definitions to the cache directory."""
        print(f"INFO [BaseToolProvider]: Saving {len(tools)} tools to cache at {self.cache_dir}...")
        for tool_name, tool_def in tools.items():
            # Sanitize tool_name for use as a filename
            filename_safe_tool_name = re.sub(r'[^\w\.-]', '_', tool_name)
            output_filepath = self.cache_dir / f"{filename_safe_tool_name}.json"
            try:
                with open(output_filepath, 'w') as f:
                    json.dump(tool_def, f, indent=2)
            except IOError as e:
                print(f"ERROR [BaseToolProvider]: Error writing tool definition for {tool_name} to {output_filepath}: {e}")

    async def get_tools(self) -> dict[str, dict]:
        """
        Main public method to get tools.
        Tries to load from cache first, otherwise generates them.
        """
        cached_tools = self._load_from_cache()
        if cached_tools:
            print(f"INFO [{self.__class__.__name__}]: Loaded {len(cached_tools)} tools from cache.")
            return cached_tools
        
        print(f"INFO [{self.__class__.__name__}]: Cache is empty or invalid. Generating tools...")
        generated_tools = await self._generate_tools()
        
        if generated_tools:
            self._save_to_cache(generated_tools)
        
        return generated_tools
