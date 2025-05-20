# Polkaquery
# Copyright (C) 2024 YOUR_NAME_OR_ORGANIZATION_NAME
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

import requests
import re
import yaml  # PyYAML
import json
from bs4 import BeautifulSoup # Still imported but less critical for YAML extraction
import time # For rate limiting/delays
import traceback # For detailed error logging
import os # For directory creation
import pathlib # For path manipulation

LLMS_TXT_URL = "https://support.subscan.io/llms.txt"
# Define the directory where individual tool JSON files will be saved
TOOLS_OUTPUT_DIRECTORY = "polkaquery_tool_definitions"
REQUEST_DELAY_SECONDS = 0.5

def fetch_content(url: str) -> str | None:
    """Fetches text content from a URL with a small delay."""
    print(f"Fetching: {url}")
    try:
        time.sleep(REQUEST_DELAY_SECONDS)
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def generate_tool_name(category: str, summary: str, path: str) -> str:
    """Generates a consistent and unique tool name."""
    clean_summary = re.sub(r'\W+', '_', summary.lower()).strip('_')
    if not category: 
        category = "general"
    clean_category = re.sub(r'\W+', '_', category.lower()).strip('_')

    if clean_summary.startswith(clean_category) and clean_category:
        name = clean_summary
    else:
        name = f"{clean_category}_{clean_summary}" if clean_category else clean_summary
    
    name = name.replace("__", "_")
    
    if not clean_summary or len(clean_summary) < 5 :
        path_parts = [part for part in path.split('/') if part and part not in ['api', 'scan', 'v2']]
        name_from_path = "_".join(path_parts)
        if name_from_path:
            if clean_category and name_from_path.startswith(clean_category):
                 return name_from_path.replace("__", "_")
            return f"{clean_category}_{name_from_path}".replace("__", "_") if clean_category else name_from_path.replace("__", "_")
    return name


def parse_llms_txt(content: str) -> list[dict]:
    """Parses the llms.txt content to get API names and their doc URLs."""
    apis = []
    current_category = "general" 
    api_line_pattern = re.compile(r"^- (\w+)\s+\[([^\]]+)\]\(([^)]+\.md)\):?\s*(.*)")
    category_pattern = re.compile(r"^##\s*([\w\s\/]+)") 

    for line in content.splitlines():
        line = line.strip()
        if not line: continue

        category_match = category_pattern.match(line)
        if category_match:
            raw_category_name = category_match.group(1).strip()
            current_category = re.sub(r'[\s\/]+', '_', raw_category_name.lower())
            print(f"--- Switched to category: {current_category} ---")
            continue
        
        api_match = api_line_pattern.match(line)
        if api_match:
            line_category, name, url_path, description = api_match.groups()
            final_category = line_category.strip().lower() if line_category else current_category
            apis.append({
                "category": final_category,
                "name_from_llms_txt": name.strip(),
                "doc_url": url_path,
                "initial_description": description.strip()
            })
        elif line.startswith("- [") and (line.endswith("):") or line.endswith("): ")):
            pass 
        elif line.startswith("- "):
             print(f"Warning: Could not fully parse potential API line: {line}")
    return apis


def extract_openapi_yaml_from_markdown_string(markdown_content: str) -> str | None:
    """
    Extracts the OpenAPI YAML block directly from a markdown string using regex.
    """
    match = re.search(r"```yaml\s*\n(?P<yaml_content>.*?)\n```", markdown_content, re.DOTALL)
    if match:
        return match.group("yaml_content").strip()
    match = re.search(r"```\s*\n(?P<content>openapi:.*?)\n```", markdown_content, re.DOTALL)
    if match:
        potential_yaml = match.group("content").strip()
        if potential_yaml.startswith("openapi:") and "paths:" in potential_yaml:
            return potential_yaml
    print("Warning: Could not find YAML block using regex on markdown string.")
    return None


def transform_openapi_to_tool(openapi_data: dict, api_info: dict) -> dict | None:
    """
    Transforms a parsed OpenAPI spec into our tool definition format.
    """
    try:
        api_path = list(openapi_data.get("paths", {}).keys())[0]
        path_item = openapi_data["paths"][api_path]
        api_method = list(path_item.keys())[0].upper()
        method_item = path_item[list(path_item.keys())[0]]

        summary = method_item.get("summary", api_info.get("name_from_llms_txt", "Unnamed API"))
        tool_name = generate_tool_name(api_info["category"], summary, api_path)
        
        description = method_item.get("description") or summary or api_info.get("initial_description", "No description available.")
        description = description.replace("\n", " ").replace("\r", " ").strip()

        parameters_schema = {"type": "object", "properties": {}, "required": []}
        
        if "requestBody" in method_item:
            content = method_item["requestBody"].get("content", {})
            json_schema_ref_obj = content.get("application/json", {}).get("schema", {})
            param_schema_def = {}
            if "$ref" in json_schema_ref_obj:
                schema_name = json_schema_ref_obj["$ref"].split('/')[-1]
                param_schema_def = openapi_data.get("components", {}).get("schemas", {}).get(schema_name, {})
            else:
                param_schema_def = json_schema_ref_obj

            if param_schema_def.get("type") == "object" and "properties" in param_schema_def:
                for prop_name, prop_details in param_schema_def.get("properties", {}).items():
                    param_info = {"type": prop_details.get("type", "string"), 
                                  "description": prop_details.get("description", "")} # Ensure description is always present
                    for key in ["enum", "default", "minimum", "maximum", "example", "examples"]:
                        if key in prop_details:
                            if key == "examples" and isinstance(prop_details[key], list) and prop_details[key]:
                                param_info["example"] = prop_details[key][0]
                            elif key != "examples":
                                param_info[key] = prop_details[key]
                    parameters_schema["properties"][prop_name] = param_info
                parameters_schema["required"] = param_schema_def.get("required", [])
        
        for param_spec in method_item.get("parameters", []):
            param_name = param_spec.get("name")
            param_in = param_spec.get("in")
            if param_name and param_in in ["query", "path"]:
                param_schema_details = param_spec.get("schema", {})
                param_info = {"type": param_schema_details.get("type", "string"), 
                              "description": param_spec.get("description", "")} # Ensure description is always present
                if "default" in param_schema_details: param_info["default"] = param_schema_details["default"]
                parameters_schema["properties"][param_name] = param_info
                if param_spec.get("required"):
                    if param_name not in parameters_schema["required"]:
                        parameters_schema["required"].append(param_name)
        
        response_desc = f"Returns JSON data for {summary}."

        return {
            "name": tool_name,
            "description": description,
            "api_path": api_path,
            "api_method": api_method,
            "parameters": parameters_schema,
            "response_schema_description": response_desc
        }
    except IndexError:
        print(f"  Error: Could not determine API path or method for '{api_info.get('name_from_llms_txt', 'Unknown API')}' (URL: {api_info.get('doc_url', 'N/A')}): OpenAPI structure might be unexpected.")
        return None
    except Exception as e:
        print(f"  Error transforming OpenAPI for '{api_info.get('name_from_llms_txt', 'Unknown API')}' (URL: {api_info.get('doc_url', 'N/A')}): {e}")
        traceback.print_exc()
        return None

def main(process_limit: int | None = None, specific_url_segment: str | None = None):
    """
    Main function to parse Subscan API specs and generate individual tool JSON files.
    """
    print("Starting Subscan API Specification Parser...")
    
    # Create the output directory if it doesn't exist
    output_dir_path = pathlib.Path(TOOLS_OUTPUT_DIRECTORY)
    try:
        output_dir_path.mkdir(parents=True, exist_ok=True)
        print(f"Ensured output directory exists: {output_dir_path.resolve()}")
    except OSError as e:
        print(f"Error creating output directory {TOOLS_OUTPUT_DIRECTORY}: {e}")
        return

    llms_txt_content = fetch_content(LLMS_TXT_URL)
    if not llms_txt_content:
        print("Failed to fetch llms.txt. Exiting.")
        return

    print("\nParsing llms.txt to identify API documentation pages...")
    apis_info = parse_llms_txt(llms_txt_content)
    print(f"Found {len(apis_info)} potential API endpoints listed in llms.txt.")

    successful_tool_definitions = 0
    seen_tool_filenames = set() # To handle potential duplicate tool names becoming duplicate filenames

    for i, api_info in enumerate(apis_info):
        if specific_url_segment and specific_url_segment not in api_info['doc_url']:
            continue

        print(f"\nProcessing API {i+1}/{len(apis_info)}: \"{api_info['name_from_llms_txt']}\"")
        print(f"  Doc URL: {api_info['doc_url']}")

        markdown_page_content = fetch_content(api_info['doc_url'])
        if not markdown_page_content:
            print(f"  Could not fetch doc page content. Skipping.")
            continue

        openapi_yaml_str = extract_openapi_yaml_from_markdown_string(markdown_page_content)
        
        if not openapi_yaml_str:
            print(f"  Could not extract OpenAPI YAML from markdown content. Skipping.")
            continue
        
        try:
            openapi_data = yaml.safe_load(openapi_yaml_str)
            if not isinstance(openapi_data, dict) or "paths" not in openapi_data:
                print(f"  Parsed YAML does not seem to be a valid OpenAPI spec (missing 'paths' or not a dict). Skipping.")
                continue
        except yaml.YAMLError as e:
            print(f"  Error parsing YAML: {e}. YAML that failed:\n{openapi_yaml_str[:500]}...")
            continue
        
        tool_definition = transform_openapi_to_tool(openapi_data, api_info)
        if tool_definition:
            tool_name = tool_definition['name']
            # Sanitize tool_name for use as a filename (though generate_tool_name should already do a good job)
            filename_safe_tool_name = re.sub(r'[^\w\.-]', '_', tool_name) 
            output_filename = f"{filename_safe_tool_name}.json"
            output_filepath = output_dir_path / output_filename

            # Handle potential filename collisions if generate_tool_name isn't perfectly unique
            # or if different summaries lead to same sanitized name.
            counter = 1
            base_output_filename = output_filename
            while output_filepath.exists() or output_filename in seen_tool_filenames:
                print(f"Warning: Filename {output_filepath} already exists or name collision. Attemping to rename.")
                output_filename = f"{filename_safe_tool_name}_{counter}.json"
                output_filepath = output_dir_path / output_filename
                counter += 1
                if counter > 10: # Safety break
                    print(f"Error: Could not find a unique filename for tool {tool_name} after 10 attempts. Skipping.")
                    break
            if counter > 10:
                continue

            try:
                with open(output_filepath, 'w') as f:
                    json.dump(tool_definition, f, indent=2)
                print(f"  Successfully transformed and saved tool: {tool_name} to {output_filepath}")
                seen_tool_filenames.add(output_filename)
                successful_tool_definitions += 1
            except IOError as e:
                print(f"  Error writing tool definition for {tool_name} to {output_filepath}: {e}")

        else:
            print(f"  Failed to transform to tool definition (see errors above).")

        if process_limit is not None and successful_tool_definitions >= process_limit:
            print(f"\nReached processing limit of {process_limit} successfully generated tools.")
            break
            
    print(f"\nParser finished. Generated {successful_tool_definitions} unique tool definition files in '{TOOLS_OUTPUT_DIRECTORY}/'")

if __name__ == "__main__":
    # To process only the "Account assets changed history" example:
    # main(specific_url_segment="api-9779503.md", process_limit=1) # Limit to 1 successful for this specific test
    
    # To process a few more for testing (e.g., first 5 successfully transformed tools):
    # main(process_limit=5)
    
    # To process all APIs (can take time, use with caution):
    main()
