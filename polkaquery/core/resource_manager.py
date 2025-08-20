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
import httpx
import google.generativeai as genai
from substrateinterface import SubstrateInterface
import traceback

from polkaquery.config import Settings

# Attempt to import TavilyClient
try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

class ResourceManager:
    """
    Central service for initializing and providing access to shared application resources.
    This includes API clients and loaded tool definitions.
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Clients are lazily initialized
        self._http_client: httpx.AsyncClient | None = None
        self._gemini_model: genai.GenerativeModel | None = None
        self._tavily_client: 'TavilyClient' | None = None
        self._assethub_rpc_client: SubstrateInterface | None = None

        # Tool definitions are loaded at initialization
        self.subscan_tools: dict[str, dict] = {}
        self.assethub_tools: dict[str, dict] = {}
        self._load_all_tools()

    def _load_all_tools(self):
        """Loads all tool definitions from the filesystem into memory."""
        base_path = pathlib.Path(self.settings.tools_output_directory)
        
        # Load Subscan tools
        subscan_path = base_path / "subscan"
        if subscan_path.is_dir():
            for tool_file in glob.glob(str(subscan_path / "*.json")):
                try:
                    with open(tool_file, 'r') as f:
                        tool_def = json.load(f)
                        if tool_def.get("name"):
                            self.subscan_tools[tool_def["name"]] = tool_def
                except Exception as e:
                    print(f"Warning: Failed to load Subscan tool {tool_file}: {e}")
            # Add internet search tool to subscan tools
            self.subscan_tools["internet_search"] = INTERNET_SEARCH_TOOL
            print(f"INFO [ResourceManager]: Loaded {len(self.subscan_tools)} Subscan tools.")
        else:
            print(f"ERROR [ResourceManager]: Subscan tools directory not found at {subscan_path}")

        # Load AssetHub tools
        assethub_path = base_path / "assethub"
        if assethub_path.is_dir():
            for tool_file in glob.glob(str(assethub_path / "*.json")):
                try:
                    with open(tool_file, 'r') as f:
                        tool_def = json.load(f)
                        if tool_def.get("name"):
                            self.assethub_tools[tool_def["name"]] = tool_def
                except Exception as e:
                    print(f"Warning: Failed to load AssetHub tool {tool_file}: {e}")
            # Add internet search tool to assethub tools
            self.assethub_tools["internet_search"] = INTERNET_SEARCH_TOOL
            print(f"INFO [ResourceManager]: Loaded {len(self.assethub_tools)} AssetHub tools.")
        else:
            print(f"ERROR [ResourceManager]: AssetHub tools directory not found at {assethub_path}")

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Provides a singleton instance of the httpx.AsyncClient."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=20.0)
        return self._http_client

    @property
    def gemini_model(self) -> genai.GenerativeModel:
        """Provides a singleton instance of the Gemini GenerativeModel."""
        if self._gemini_model is None:
            if self.settings.google_gemini_api_key:
                try:
                    genai.configure(api_key=self.settings.google_gemini_api_key)
                    self._gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                    print("INFO [ResourceManager]: Google Gemini API configured successfully.")
                except Exception as e:
                    print(f"ERROR [ResourceManager]: Failed to configure Gemini API: {e}")
                    raise RuntimeError("Gemini API configuration failed")
            else:
                raise ValueError("GOOGLE_GEMINI_API_KEY is not set.")
        return self._gemini_model

    @property
    def tavily_client(self) -> 'TavilyClient | None':
        """Provides a singleton instance of the TavilyClient, if available and configured."""
        if self._tavily_client is None and TavilyClient is not None and self.settings.tavily_api_key:
            try:
                self._tavily_client = TavilyClient(api_key=self.settings.tavily_api_key)
                print("INFO [ResourceManager]: TavilyClient initialized successfully.")
            except Exception as e:
                print(f"Warning [ResourceManager]: Failed to initialize TavilyClient: {e}")
        return self._tavily_client

    @property
    def assethub_rpc_client(self) -> SubstrateInterface | None:
        """Provides a singleton instance of the SubstrateInterface client for AssetHub."""
        if self._assethub_rpc_client is None and self.settings.onfinality_api_key:
            ws_url = f"{self.settings.assethub_ws_url}?apikey={self.settings.onfinality_api_key}"
            try:
                self._assethub_rpc_client = SubstrateInterface(url=ws_url)
                self._assethub_rpc_client.init_runtime()
                print(f"INFO [ResourceManager]: AssetHub RPC client connected to {ws_url}")
            except Exception as e:
                print(f"CRITICAL ERROR [ResourceManager]: Could not connect AssetHub RPC client. Error: {e}")
                traceback.print_exc()
                # We don't raise here, but the property will return None
        return self._assethub_rpc_client

    async def shutdown(self):
        """Gracefully closes all open connections."""
        if self._http_client:
            await self._http_client.aclose()
            print("INFO [ResourceManager]: HTTP client shut down.")
        if self._assethub_rpc_client and self._assethub_rpc_client.websocket:
            self._assethub_rpc_client.close()
            print("INFO [ResourceManager]: AssetHub RPC client connection closed.")

# Define and add the Internet Search tool
INTERNET_SEARCH_TOOL = {
  "name": "internet_search",
  "description": "Performs a general internet search to find information when the user's query is broad, asks for general knowledge, explanations, news, or topics not covered by specific blockchain data APIs (like Subscan tools). Use this if no specific Subscan tool directly matches the query's intent for on-chain data.",
  "api_path": None, # Not a Subscan API
  "api_method": None, # Not a Subscan API
  "parameters": {
    "type": "object",
    "properties": {
      "search_query": {
        "type": "string",
        "description": "A concise and effective search query derived from the user's original question, suitable for a web search engine."
      }
    },
    "required": ["search_query"]
  },
  "response_schema_description": "Returns a text summary of relevant information found on the internet."
}
