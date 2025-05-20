# formatter.py
from fastapi import HTTPException

def format_response(intent: str, subscan_data: dict) -> str:
    """
    Formats the raw JSON data from Subscan into a user-friendly string.
    """
    try:
        data = subscan_data.get("data") # Subscan usually wraps results in 'data'
        if not data:
            # Handle cases where data field is missing or null but code was 0
            return f"Received success code from Subscan, but no data found for intent '{intent}'."

        if intent == "get_balance":
            # --- Format Balance ---
            # IMPORTANT: Structure depends heavily on the actual Subscan response JSON!
            # This is a GUESS based on potential v2 structures. Need to inspect actual response.
            # Example: Assume v2 /api/v2/scan/accounts returns a list, take the first.
            if isinstance(data, list) and len(data) > 0:
                 account_info = data[0]
                 address = account_info.get("address")
                 balance = account_info.get("balance") # Total balance might be 'balance'
                 # Subscan balances are often strings representing Planck units. Convert to DOT.
                 # Polkadot has 10 decimal places.
                 balance_dot = format_planck(balance, 10) if balance else "0"
                 return f"The total balance of address {address} is approximately {balance_dot} DOT."
            elif isinstance(data, dict): # Handle single object response if applicable
                 address = data.get("address")
                 balance = data.get("balance")
                 balance_dot = format_planck(balance, 10) if balance else "0"
                 return f"The total balance of address {address} is approximately {balance_dot} DOT."
            else:
                 return "Could not parse balance information from Subscan response."


        elif intent == "get_extrinsic":
             # --- Format Extrinsic ---
             # IMPORTANT: Check Subscan JSON structure for /api/scan/extrinsic
             extrinsic_hash = data.get("extrinsic_hash")
             block_num = data.get("block_num")
             success = data.get("success", False) # Check how success is indicated
             module = data.get("call_module")
             call = data.get("call_module_function")
             fee = format_planck(data.get("fee"), 10) if data.get("fee") else "N/A"
             status = "successful" if success else "failed"

             return (f"Extrinsic {extrinsic_hash} in block {block_num} was {status}. "
                     f"It called {module}.{call} with a fee of {fee} DOT.")

        elif intent == "get_latest_block":
            # --- Format Latest Block ---
            # IMPORTANT: Check Subscan JSON structure for /api/scan/blocks
            # Assuming it returns a list of blocks, we want the first one (latest)
            if isinstance(data.get("blocks"), list) and len(data["blocks"]) > 0:
                latest_block = data["blocks"][0]
                block_num = latest_block.get("block_num")
                timestamp = latest_block.get("block_timestamp") # Unix timestamp
                extrinsics_count = latest_block.get("extrinsics_count")
                events_count = latest_block.get("event_count")
                # Convert timestamp to readable format if desired
                return (f"The latest finalized block is #{block_num}. "
                        f"It contained {extrinsics_count} extrinsics and {events_count} events.")
            else:
                return "Could not parse latest block information from Subscan response."

        else:
            return f"Formatting not implemented for intent '{intent}' yet."

    except Exception as e:
        # Catch errors during parsing/formatting
        print(f"Error formatting response for intent {intent}: {e}")
        # Log the subscan_data that caused the error if possible (careful with size/secrets)
        return f"Error processing the data received from Subscan for intent '{intent}'."


def format_planck(value_str: str | None, decimals: int) -> str:
    """
    Helper function to convert Planck units (string) to float DOT/KSM etc. (string).
    Handles potential None input and large numbers.
    """
    if value_str is None or not value_str.isdigit():
        return "N/A"
    try:
        value_int = int(value_str)
        divisor = 10**decimals
        float_value = value_int / divisor
        # Format nicely, potentially trimming trailing zeros
        return f"{float_value:,.{decimals}f}".rstrip('0').rstrip('.')
    except (ValueError, TypeError):
        return "Invalid Format"