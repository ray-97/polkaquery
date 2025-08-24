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
from polkaquery.providers.base import BaseToolProvider
from polkaquery.providers.subscan import SubscanToolProvider
from polkaquery.providers.assethub import AssetHubToolProvider

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

        # Tool providers are initialized here
        self.subscan_provider: BaseToolProvider = SubscanToolProvider(settings, self.http_client)
        self.assethub_provider: BaseToolProvider = AssetHubToolProvider(settings)

        # Tool definitions are loaded via the providers on startup
        self.subscan_tools: dict[str, dict] = {}
        self.assethub_tools: dict[str, dict] = {}

        # Prompts are loaded from files on startup
        self.router_prompt: str = ""
        self.tool_recognizer_prompt: str = ""
        self.assethub_recognizer_prompt: str = ""
        self.final_answer_prompt: str = ""
        self.error_translator_prompt: str = ""
        self._load_prompts()

    def _load_prompts(self):
        """Loads all prompt templates from the filesystem."""
        print("INFO [ResourceManager]: Loading prompts...")
        try:
            prompt_dir = pathlib.Path("polkaquery/prompts")
            self.router_prompt = (prompt_dir / "router_prompt.txt").read_text()
            self.tool_recognizer_prompt = (prompt_dir / "tool_recognizer_prompt.txt").read_text()
            self.assethub_recognizer_prompt = (prompt_dir / "assethub_recognizer_prompt.txt").read_text()
            self.final_answer_prompt = (prompt_dir / "final_answer_prompt.txt").read_text()
            self.error_translator_prompt = (prompt_dir / "error_translator_prompt.txt").read_text()
            print("INFO [ResourceManager]: All prompts loaded successfully.")
        except FileNotFoundError as e:
            print(f"ERROR [ResourceManager]: Prompt file not found: {e}. The application may not function correctly.")
        except Exception as e:
            print(f"ERROR [ResourceManager]: An unexpected error occurred while loading prompts: {e}")

    async def load_tools(self):
        """Loads tools from all providers into memory."""
        print("INFO [ResourceManager]: Loading tools from all providers...")
        self.subscan_tools = await self.subscan_provider.get_tools()
        self.assethub_tools = await self.assethub_provider.get_tools()
        # Add internet search tool after loading from providers
        if self.subscan_tools:
            self.subscan_tools["internet_search"] = INTERNET_SEARCH_TOOL
        if self.assethub_tools:
            self.assethub_tools["internet_search"] = INTERNET_SEARCH_TOOL

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
