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
import re
import yaml
import asyncio
import traceback

from polkaquery.providers.base import BaseToolProvider
from polkaquery.config import Settings

LLMS_TXT_URL = "https://support.subscan.io/llms.txt"
REQUEST_DELAY_SECONDS = 0.2

class SubscanToolProvider(BaseToolProvider):
    """Generates tool definitions by scraping Subscan's API documentation."""
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        super().__init__(settings, cache_subdirectory="subscan")
        self.client = client

    async def _fetch_content(self, url: str) -> str | None:
        """Fetches text content from a URL with a small delay."""
        print(f"INFO [SubscanToolProvider]: Fetching: {url}")
        try:
            await asyncio.sleep(REQUEST_DELAY_SECONDS)
            response = await self.client.get(url, timeout=15)
            response.raise_for_status()
            return response.text
        except httpx.RequestError as e:
            print(f"ERROR [SubscanToolProvider]: Error fetching {url}: {e}")
            return None

    def _generate_tool_name(self, category: str, summary: str, path: str) -> str:
        """Generates a consistent and unique tool name."""
        clean_summary = re.sub(r'\W+', '_', summary.lower()).strip('_')
        if not category: category = "general"
        clean_category = re.sub(r'\W+', '_', category.lower()).strip('_')

        name = f"{clean_category}_{clean_summary}" if clean_category and not clean_summary.startswith(clean_category) else clean_summary
        name = name.replace("__", "_")
        
        if not clean_summary or len(clean_summary) < 5:
            path_parts = [part for part in path.split('/') if part and part not in ['api', 'scan', 'v2']]
            name_from_path = "_".join(path_parts)
            if name_from_path:
                return f"{clean_category}_{name_from_path}".replace("__", "_") if clean_category and not name_from_path.startswith(clean_category) else name_from_path.replace("__", "_")
        return name

    def _parse_llms_txt(self, content: str) -> list[dict]:
        """Parses the llms.txt content to get API names and their doc URLs."""
        apis = []
        current_category = "general"
        api_line_pattern = re.compile(r"^- (\w+)\s+\[([^\]]+)\]([^\]]+\.md)\):?\s*(.*)")
        category_pattern = re.compile(r"^##\s*([\w\s\/]+)")

        for line in content.splitlines():
            line = line.strip()
            if not line: continue

            category_match = category_pattern.match(line)
            if category_match:
                current_category = re.sub(r'[\s\/]+', '_', category_match.group(1).strip().lower())
                continue
            
            api_match = api_line_pattern.match(line)
            if api_match:
                line_category, name, url_path, description = api_match.groups()
                apis.append({
                    "category": line_category.strip().lower() if line_category else current_category,
                    "name_from_llms_txt": name.strip(),
                    "doc_url": url_path,
                    "initial_description": description.strip()
                })
        return apis

    def _extract_openapi_yaml(self, markdown_content: str) -> str | None:
        match = re.search(r"```yaml\s*\n(?P<yaml_content>.*?)\n```", markdown_content, re.DOTALL)
        if match:
            return match.group("yaml_content").strip()
        return None

    def _transform_openapi_to_tool(self, openapi_data: dict, api_info: dict) -> dict | None:
        try:
            api_path = list(openapi_data.get("paths", {}).keys())[0]
            path_item = openapi_data["paths"][api_path]
            api_method = list(path_item.keys())[0].upper()
            method_item = path_item[list(path_item.keys())[0]]

            summary = method_item.get("summary", api_info.get("name_from_llms_txt", "Unnamed"))
            tool_name = self._generate_tool_name(api_info["category"], summary, api_path)
            
            description = (method_item.get("description") or summary).replace("\n", " ").strip()

            parameters_schema = {"type": "object", "properties": {}, "required": []}
            
            if "requestBody" in method_item:
                content = method_item["requestBody"].get("content", {})
                json_schema_ref = content.get("application/json", {}).get("schema", {})
                param_schema = openapi_data.get("components", {}).get("schemas", {}).get(json_schema_ref.get("$ref", "").split('/')[-1]) if "$ref" in json_schema_ref else json_schema_ref

                if param_schema.get("type") == "object":
                    parameters_schema["properties"] = {k: {"type": v.get("type", "string"), "description": v.get("description", "")} for k, v in param_schema.get("properties", {}).items()}
                    parameters_schema["required"] = param_schema.get("required", [])
            
            return {
                "name": tool_name,
                "description": description,
                "api_path": api_path,
                "api_method": api_method,
                "parameters": parameters_schema,
                "response_schema_description": f"Returns JSON data for {summary}."
            }
        except Exception as e:
            print(f"ERROR [SubscanToolProvider]: Failed to transform OpenAPI for '{api_info.get('name_from_llms_txt')}': {e}")
            traceback.print_exc()
            return None

    async def _generate_tools(self) -> dict[str, dict]:
        """Fetches and processes Subscan API specs to generate tool definitions."""
        print("INFO [SubscanToolProvider]: Starting Subscan API Specification processing...")
        llms_txt_content = await self._fetch_content(LLMS_TXT_URL)
        if not llms_txt_content:
            print("ERROR [SubscanToolProvider]: Failed to fetch llms.txt. Aborting tool generation.")
            return {}

        apis_info = self._parse_llms_txt(llms_txt_content)
        print(f"INFO [SubscanToolProvider]: Found {len(apis_info)} potential API endpoints listed.")

        tools = {}
        for api_info in apis_info:
            markdown_content = await self._fetch_content(api_info['doc_url'])
            if not markdown_content: continue

            openapi_yaml_str = self._extract_openapi_yaml(markdown_content)
            if not openapi_yaml_str: continue
            
            try:
                openapi_data = yaml.safe_load(openapi_yaml_str)
                if not isinstance(openapi_data, dict) or "paths" not in openapi_data:
                    continue
            except yaml.YAMLError as e:
                print(f"ERROR [SubscanToolProvider]: Error parsing YAML for {api_info['doc_url']}: {e}")
                continue
            
            tool_definition = self._transform_openapi_to_tool(openapi_data, api_info)
            if tool_definition:
                tools[tool_definition["name"]] = tool_definition
        
        print(f"INFO [SubscanToolProvider]: Successfully generated {len(tools)} tool definitions.")
        return tools
