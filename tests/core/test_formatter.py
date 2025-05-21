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
        return datetime.datetime.fromtimestamp(unix_timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')
    except (ValueError, TypeError):
        return "Invalid Timestamp"

def format_response_for_llm(intent_tool_name: str, subscan_data: dict, network_name: str, decimals: int, symbol: str, original_params: dict = None) -> dict:
    """
    Pre-formats the raw JSON data from Subscan into a structured dictionary
    intended to be used as input for a final LLM answer synthesis step.
    """
    if original_params is None: original_params = {}
    output = {
        "intent_processed": intent_tool_name,
        "network": network_name,
        "status": "success", 
        "summary": "", 
        "key_data": {}, 
        "raw_data_snippet": None 
    }

    try:
        if subscan_data.get("code") != 0:
            output["status"] = "error"
            output["summary"] = f"Subscan API (or search tool) reported an error for '{intent_tool_name}' on {network_name}."
            output["key_data"] = {
                "error_code": subscan_data.get("code"),
                "error_message": subscan_data.get("message", "Unknown API error.")
            }
            return output

        data = subscan_data.get("data")
        if data is None and intent_tool_name != "internet_search": # internet_search might have code:0 but data:None if search fails gracefully
            # For Subscan tools, if data is None after code:0, it's usually a "not found" type scenario
            output["status"] = "nodata"
            output["summary"] = f"No specific data was found by Subscan for '{intent_tool_name}' on {network_name} with parameters {original_params}."
            return output
        elif data is None and intent_tool_name == "internet_search": # Specific handling for internet search if data is None
             output["status"] = "error" # Treat as error if data is None after code:0 from search
             output["summary"] = f"Internet search for '{original_params.get('search_query', 'query')}' returned no data object, though reported success code."
             output["key_data"] = {"message": "Search tool returned success code but no data."}
             return output


        if intent_tool_name == "account_balance" or intent_tool_name == "general_get_balance": 
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

        elif intent_tool_name == "extrinsic_extrinsic_detail" or intent_tool_name == "general_get_extrinsic": 
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
        
        elif intent_tool_name == "block_blocks_list" and original_params.get("row") == 1 and original_params.get("page",0) == 0 : 
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
            search_results = data.get("results", []) 
            query_used = data.get('query_used', original_params.get('search_query', 'N/A'))
            output["summary"] = f"Internet search results for query: '{query_used}'"
            # Always include answer_summary key, even if its value is None
            output["key_data"] = {
                "search_provider": data.get("search_provider", "Unknown"),
                "query_used": query_used,
                "answer_summary": data.get("answer_summary"), # Will be None if not present in data
                "count": len(search_results),
                "results_preview": [ 
                    {"title": res.get("title"), "url": res.get("url"), "snippet": str(res.get("content", ""))[:200] + "..."} 
                    for res in search_results[:3] 
                ]
            }
            if not search_results and not data.get("answer_summary"): # If no results AND no direct answer
                output["summary"] = f"No specific information found by internet search for: '{query_used}'"
                output["status"] = "nodata"
            elif not search_results and data.get("answer_summary"): # Direct answer but no separate results
                output["summary"] = f"Internet search provided a direct summary for: '{query_used}'"
                # key_data already has answer_summary
            elif search_results and not data.get("answer_summary"): # Results but no direct answer
                output["summary"] = f"Found {len(search_results)} internet search results for: '{query_used}'"


        else: # Generic Handler for other Subscan tools
            output["summary"] = f"Data received for '{intent_tool_name}' on {network_name}."
            if isinstance(data, list):
                output["key_data"]["count"] = len(data)
                output["key_data"]["sample_items"] = data[:3] 
                output["summary"] += f" Found {len(data)} items."
            elif isinstance(data, dict):
                list_keys = [k for k, v in data.items() if isinstance(v, list) and v] 
                if list_keys:
                    primary_list_key = list_keys[0]
                    primary_list = data[primary_list_key]
                    output["key_data"]["count"] = len(primary_list)
                    output["key_data"][f"sample_{primary_list_key}"] = primary_list[:3]
                    output["summary"] += f" Found {len(primary_list)} items under '{primary_list_key}'."
                    other_data = {k:v for k,v in data.items() if k != primary_list_key and not isinstance(v, (list, dict))} 
                    if other_data: output["key_data"]["other_details"] = other_data
                else: 
                    output["key_data"] = data 
                    output["summary"] += " Retrieved detailed object."
            else: 
                output["key_data"]["value"] = data
            
    except Exception as e:
        import traceback
        print(f"Error in formatter for intent {intent_tool_name} on network {network_name}: {e}")
        traceback.print_exc()
        output["status"] = "error"
        output["summary"] = f"An error occurred while formatting the data for '{intent_tool_name}'."
        output["key_data"] = {"formatter_error": str(e)}

    return output
