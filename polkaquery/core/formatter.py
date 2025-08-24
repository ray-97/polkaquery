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

import datetime # For timestamp conversion
import json     # For handling raw data snippets

def format_planck(value_str: str | None, decimals: int) -> str:
    """Helper function to convert Planck units (string) to token units (string)."""
    if value_str is None or not value_str.isdigit():
        return "N/A"
    try:
        if decimals <= 0: return value_str
        value_int = int(value_str)
        divisor = 10**decimals
        float_value = value_int / divisor
        formatted = f"{float_value:,.{decimals}f}".rstrip('0').rstrip('.')
        return formatted if formatted else "0"
    except (ValueError, TypeError):
        return "Invalid Planck Value"

def format_timestamp(unix_timestamp: int | None) -> str:
    """Formats a Unix timestamp into a human-readable ISO-like string."""
    if unix_timestamp is None:
        return "N/A"
    try:
        # Using ISO format is often good for LLMs to parse if needed,
        # but a more human-friendly one is also fine.
        return datetime.datetime.fromtimestamp(unix_timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')
    except (ValueError, TypeError):
        return "Invalid Timestamp"

def format_subscan_response_for_llm(intent_tool_name: str, subscan_data: dict, network_name: str, decimals: int, symbol: str, original_params: dict = None) -> dict:
    """
    Pre-formats the raw JSON data from Subscan into a structured dictionary
    intended to be used as input for a final LLM answer synthesis step.

    Args:
        intent_tool_name: The name of the tool/intent used.
        subscan_data: The raw JSON dictionary received from Subscan.
        network_name: The name of the network queried.
        decimals: The number of decimal places for the network's native token.
        symbol: The symbol of the network's native token.
        original_params: Parameters extracted by the first LLM call, for context.

    Returns:
        A dictionary containing a summary and key extracted data.
    """
    if original_params is None: original_params = {}
    output = {
        "intent_processed": intent_tool_name,
        "network": network_name,
        "status": "success", # Assume success initially
        "summary": "", # To be filled by specific handlers
        "key_data": {}, # To be filled by specific handlers
        "raw_data_snippet": None # Optionally include a snippet for LLM if needed
    }

    try:
        # Handle Subscan API level errors (code != 0)
        if subscan_data.get("code") != 0:
            output["status"] = "error"
            output["summary"] = f"Subscan API reported an error for '{intent_tool_name}' on {network_name}."
            output["key_data"] = {
                "error_code": subscan_data.get("code"),
                "error_message": subscan_data.get("message", "Unknown Subscan API error.")
            }
            return output

        data = subscan_data.get("data")
        if data is None: # Successful call but no specific data returned
            output["status"] = "nodata"
            output["summary"] = f"No specific data was found by Subscan for '{intent_tool_name}' on {network_name} with parameters {original_params}."
            # output["key_data"] = {"message": "No data returned by Subscan."} # Optional
            return output

        # --- Specific Handlers for known core intents ---
        if intent_tool_name == "account_balance" or intent_tool_name == "general_get_balance": # Adjust if tool name differs
            account_info = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else None
            if account_info:
                address = account_info.get("address", original_params.get("address", "N/A"))
                output["summary"] = f"Balance information for account {address} on {network_name}."
                output["key_data"] = {
                    "address": address,
                    "total_balance": f"{format_planck(account_info.get('balance'), decimals)} {symbol}",
                    "available_balance": f"{format_planck(account_info.get('available'), decimals)} {symbol}",
                    "locked_balance": f"{format_planck(account_info.get('locked'), decimals)} {symbol}",
                    "reserved_balance": f"{format_planck(account_info.get('reserved'), decimals)} {symbol}",
                }
            else:
                output["summary"] = f"Could not parse balance details for {original_params.get('address', 'the account')}."
                output["status"] = "parse_error"

        elif intent_tool_name == "extrinsic_extrinsic_detail" or intent_tool_name == "general_get_extrinsic": # Adjust if tool name differs
            extrinsic_hash = data.get("extrinsic_hash", original_params.get("hash", "N/A"))
            output["summary"] = f"Details for extrinsic {extrinsic_hash} on {network_name}."
            output["key_data"] = {
                "hash": extrinsic_hash,
                "block_number": data.get("block_num"),
                "timestamp": format_timestamp(data.get("block_timestamp")),
                "status": "successful" if data.get("success") else "failed" if data.get("success") is not None else "unknown",
                "module_call": f"{data.get('call_module', '')}.{data.get('call_module_function', '')}",
                "fee": f"{format_planck(data.get('fee'), decimals)} {symbol}",
                "signer": data.get("account_id")
            }
        
        elif intent_tool_name == "block_blocks_list" and original_params.get("row") == 1 and original_params.get("page",0) == 0 : # Heuristic for "get_latest_block"
             # This assumes get_latest_block uses the blocks_list tool with row=1, page=0
            blocks_list = data.get("blocks")
            if isinstance(blocks_list, list) and len(blocks_list) > 0:
                latest_block = blocks_list[0]
                output["summary"] = f"Latest block information for {network_name}."
                output["key_data"] = {
                    "block_number": latest_block.get("block_num"),
                    "timestamp": format_timestamp(latest_block.get("block_timestamp")),
                    "extrinsics_count": latest_block.get("extrinsics_count"),
                    "events_count": latest_block.get("event_count"),
                    "validator": latest_block.get("validator_name") or latest_block.get("validator")
                }
            else:
                output["summary"] = "Could not parse latest block details."
                output["status"] = "parse_error"

        elif intent_tool_name == "internet_search":
            search_results = data.get("results", []) # Assuming 'data' contains 'results' list from perform_internet_search
            output["summary"] = f"Internet search results for query: '{data.get('query_used', original_params.get('search_query', 'N/A'))}'"
            output["key_data"] = {
                "search_provider": data.get("search_provider", "Unknown"),
                "count": len(search_results),
                "results_preview": [ # Extract key info from each search result
                    {"title": res.get("title"), "url": res.get("url"), "snippet": res.get("content", "")[:200] + "..."} 
                    for res in search_results[:3] # Show preview for first 3
                ]
            }
            if not search_results:
                output["summary"] = f"No results found by internet search for: '{data.get('query_used', original_params.get('search_query', 'N/A'))}'"
                output["status"] = "nodata"

        # --- Generic Handler for other tools/intents ---
        # This part needs to be robust or have more specific handlers as you add tools
        else:
            output["summary"] = f"Data received for '{intent_tool_name}' on {network_name}."
            # For list-like data, provide a count and a sample
            if isinstance(data, list):
                output["key_data"]["count"] = len(data)
                output["key_data"]["sample_items"] = data[:3] # First 3 items as sample
                output["summary"] += f" Found {len(data)} items."
            elif isinstance(data, dict):
                # If it's a dictionary, check for common list patterns within it
                list_keys = [k for k, v in data.items() if isinstance(v, list) and v] # Find keys with non-empty lists
                if list_keys:
                    # Heuristic: assume the first non-empty list is the primary data
                    primary_list_key = list_keys[0]
                    primary_list = data[primary_list_key]
                    output["key_data"]["count"] = len(primary_list)
                    output["key_data"][f"sample_{primary_list_key}"] = primary_list[:3]
                    output["summary"] += f" Found {len(primary_list)} items under '{primary_list_key}'."
                    # Include other top-level dict items if they are not too large
                    other_data = {k:v for k,v in data.items() if k != primary_list_key and not isinstance(v, (list, dict))} # Simple values
                    if other_data: output["key_data"]["other_details"] = other_data

                else: # It's a dictionary without obvious lists, treat as detail object
                    output["key_data"] = data # Include the whole data dict for now
                    output["summary"] += " Retrieved detailed object."
            else: # Primitive type or something unexpected
                output["key_data"]["value"] = data
            
            # Optionally, add a snippet of raw data for the LLM if formatting is too generic
            # raw_data_str = json.dumps(data)
            # output["raw_data_snippet"] = raw_data_str[:500] + "..." if len(raw_data_str) > 500 else raw_data_str


    except Exception as e:
        import traceback
        print(f"Error in formatter for intent {intent_tool_name} on network {network_name}: {e}")
        traceback.print_exc()
        output["status"] = "error"
        output["summary"] = f"An error occurred while formatting the data for '{intent_tool_name}'."
        output["key_data"] = {"formatter_error": str(e)}
        # output["raw_data_snippet"] = json.dumps(subscan_data)[:500] + "..." # Provide raw data on formatter error

    return output

def format_assethub_response_for_llm(api_response: dict, intent_tool_name: str, network_name: str) -> dict:
    """
    Formats the raw response from an AssetHub RPC query into a structured
    dictionary suitable for the final LLM prompt.

    Args:
        api_response: The raw dictionary returned by the RPC client.
        intent_tool_name: The name of the tool that was called.
        network_name: The name of the network queried (e.g., 'assethub-polkadot-rpc').

    Returns:
        A dictionary summarizing the data.
    """
    output = {
        "intent_processed": intent_tool_name,
        "network": network_name,
        "status": "success",
        "summary": "",
        "key_data": {},
        "raw_data_snippet": None
    }

    if not api_response:
        output["status"] = "error"
        output["summary"] = f"No data was returned for the query '{intent_tool_name}'."
        return output

    if isinstance(api_response, dict) and "error" in api_response:
        output["status"] = "error"
        output["summary"] = f"An error occurred while querying AssetHub for '{intent_tool_name}': {api_response['error']}"
        return output

    # --- Data processing and summarization ---
    output["key_data"] = api_response

    # Helper function to create a clean string summary from the data
    def create_summary(data):
        if isinstance(data, dict):
            # For dictionaries, create a key-value list
            summary_parts = []
            for key, value in data.items():
                # Recursively format nested structures for readability
                if isinstance(value, (dict, list)):
                     summary_parts.append(f"{key}: (see nested data below)")
                else:
                     summary_parts.append(f"{key}: {value}")
            return ", ".join(summary_parts)
        elif isinstance(data, list):
            return f"A list of {len(data)} items was returned."
        else:
            return str(data)

    output["summary"] = f"Successfully retrieved data for '{intent_tool_name}'. {create_summary(api_response)}"
    # Optionally, provide a snippet of the raw data if it's complex
    output["raw_data_snippet"] = json.dumps(api_response, indent=2, default=str)[:1000]

    return output
