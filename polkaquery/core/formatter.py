# Polkaquery
# Copyright (C) 2025 Polkaquery_Team

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from fastapi import HTTPException # Keep if used directly, otherwise can be removed if errors are raised elsewhere
import datetime # For timestamp conversion

def format_planck(value_str: str | None, decimals: int) -> str:
    """
    Helper function to convert Planck units (string) to token units (string).
    Handles potential None input, large numbers, and non-digit strings.
    """
    if value_str is None or not value_str.isdigit():
        return "N/A"
    try:
        if decimals <= 0:
             return value_str # Treat as indivisible if decimals is 0 or less

        value_int = int(value_str)
        divisor = 10**decimals
        float_value = value_int / divisor

        # Format with commas and appropriate decimal places, remove trailing zeros
        formatted = f"{float_value:,.{decimals}f}".rstrip('0').rstrip('.')
        return formatted if formatted else "0"
    except (ValueError, TypeError) as e:
         print(f"Error formatting planck value '{value_str}' with decimals {decimals}: {e}")
         return "Invalid Format"


def format_response(intent: str, subscan_data: dict, network_name: str, decimals: int, symbol: str, params: dict = None) -> str:
    """
    Formats the raw JSON data from Subscan into a user-friendly string.

    Args:
        intent: The recognized intent.
        subscan_data: The raw JSON dictionary received from Subscan.
        network_name: The name of the network queried (e.g., "polkadot").
        decimals: The number of decimal places for the network's native token.
        symbol: The symbol of the network's native token (e.g., "DOT").
        params: Original parameters extracted from the query (e.g., for address).

    Returns:
        A formatted string summarizing the result.
    """
    if params is None: # Ensure params is a dictionary
        params = {}

    try:
        data = subscan_data.get("data")
        if data is None:
            if subscan_data.get("code") == 0:
                 return f"Subscan reported success, but no specific data was found for the request on {network_name}."
            else:
                 return f"Received error code {subscan_data.get('code')} from Subscan on {network_name}: {subscan_data.get('message', 'Unknown error')}"

        if intent == "get_balance":
            account_info = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else None
            if account_info:
                address = account_info.get("address", params.get("address", "N/A"))
                total_balance_planck = account_info.get("balance")
                available_balance_planck = account_info.get("available")
                locked_balance_planck = account_info.get("locked")
                reserved_balance_planck = account_info.get("reserved")

                total_str = format_planck(total_balance_planck, decimals)
                available_str = format_planck(available_balance_planck, decimals)
                locked_str = format_planck(locked_balance_planck, decimals)
                reserved_str = format_planck(reserved_balance_planck, decimals)

                response_parts = [f"Account {address} on {network_name}:"]
                if total_str != "N/A": response_parts.append(f"- Total Balance: {total_str} {symbol}")
                if available_str != "N/A": response_parts.append(f"- Available: {available_str} {symbol}")
                if locked_str != "N/A" and locked_str != "0": response_parts.append(f"- Locked: {locked_str} {symbol}")
                if reserved_str != "N/A" and reserved_str != "0": response_parts.append(f"- Reserved: {reserved_str} {symbol}")

                return "\n".join(response_parts) if len(response_parts) > 1 else f"Could not parse detailed balance information for {address} on {network_name} from Subscan response."
            else:
                 return f"Could not parse balance information for the requested address ({params.get('address', 'unknown')}) on {network_name}."

        elif intent == "get_extrinsic":
             extrinsic_hash = data.get("extrinsic_hash", params.get("hash", "N/A"))
             block_num = data.get("block_num")
             block_ts_unix = data.get("block_timestamp")
             success = data.get("success")
             module = data.get("call_module")
             call = data.get("call_module_function")
             fee_planck = data.get("fee")
             signer = data.get("account_id")

             status = "successful" if success else "failed" if success is not None else "status unknown"
             fee_str = format_planck(fee_planck, decimals)
             timestamp_str = datetime.datetime.fromtimestamp(block_ts_unix).strftime('%Y-%m-%d %H:%M:%S %Z') if block_ts_unix else "N/A"

             response_parts = [f"Extrinsic {extrinsic_hash} on {network_name}:"]
             if block_num is not None: response_parts.append(f"- Included in Block: {block_num} ({timestamp_str})")
             if signer: response_parts.append(f"- Signer: {signer}")
             if module and call: response_parts.append(f"- Call: {module}.{call}")
             response_parts.append(f"- Status: {status}")
             if fee_str != "N/A": response_parts.append(f"- Fee: {fee_str} {symbol}")
             return "\n".join(response_parts)

        elif intent == "get_latest_block":
            blocks_list = data.get("blocks")
            if isinstance(blocks_list, list) and len(blocks_list) > 0:
                latest_block = blocks_list[0]
                block_num = latest_block.get("block_num")
                timestamp_unix = latest_block.get("block_timestamp")
                extrinsics_count = latest_block.get("extrinsics_count")
                events_count = latest_block.get("event_count")
                validator = latest_block.get("validator_name") or latest_block.get("validator")

                timestamp_str = datetime.datetime.fromtimestamp(timestamp_unix).strftime('%Y-%m-%d %H:%M:%S %Z') if timestamp_unix else "N/A"
                response_parts = [f"Latest finalized block on {network_name} is #{block_num} ({timestamp_str})."]
                if extrinsics_count is not None: response_parts.append(f"- Contained {extrinsics_count} extrinsics and {events_count} events.")
                if validator: response_parts.append(f"- Produced by validator: {validator}")
                return "\n".join(response_parts)
            else:
                return f"Could not parse latest block information from Subscan response on {network_name}."
        else:
            return f"Formatting not implemented for intent '{intent}' on {network_name} yet."
    except Exception as e:
        print(f"Error formatting response for intent {intent} on network {network_name}: {e}")
        return f"Error processing the data received from Subscan for intent '{intent}' on {network_name}."
