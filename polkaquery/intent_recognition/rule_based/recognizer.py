# intent_recognizer.py
import re

# Example: Basic Polkadot address regex (needs refinement for different formats)
# SS58 Address Format is complex, this is a simplification
ADDRESS_REGEX = r'\b([1-9A-HJ-NP-Za-km-z]{47,48})\b'
# Example: Extrinsic/Block Hash Regex (64 hex chars + 0x prefix)
HASH_REGEX = r'\b(0x[0-9a-fA-F]{64})\b'

# todo: Refine Regex: The regex patterns for addresses and hashes need testing and refinement to be robust. SS58 addresses, in particular, have checksums and network prefixes.


def recognize_intent(query: str) -> tuple[str, dict]:
    """
    Analyzes the query to determine intent and extract parameters.
    Returns (intent_name, parameters_dict)
    """
    query_lower = query.lower()
    params = {}

    # Rule 1: Get Balance
    if "balance" in query_lower and ("account" in query_lower or "address" in query_lower):
        match = re.search(ADDRESS_REGEX, query)
        if match:
            params["address"] = match.group(1)
            return "get_balance", params
        else:
            # Might need address but didn't find one
             return "unknown", {"reason": "Balance query detected, but no valid address found."}


    # Rule 2: Get Extrinsic Details
    if ("extrinsic" in query_lower or "transaction" in query_lower) and "detail" in query_lower:
         match = re.search(HASH_REGEX, query)
         if match:
             params["hash"] = match.group(1)
             return "get_extrinsic", params
         else:
             # Might need hash but didn't find one
             return "unknown", {"reason": "Extrinsic query detected, but no valid hash found."}

    # Rule 3: Get Latest Block
    if "latest block" in query_lower or "current block" in query_lower:
        return "get_latest_block", params # No specific params needed usually

    # Add more rules here...

    # Default fallback
    return "unknown", {"reason": "Query did not match any known patterns."}