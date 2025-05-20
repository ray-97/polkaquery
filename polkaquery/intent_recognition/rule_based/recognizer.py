# Polkaquery
# Copyright (C) 2025 Ray

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

import re

# Example: Basic Polkadot address regex (needs refinement for different formats)
ADDRESS_REGEX = r'\b([1-9A-HJ-NP-Za-km-z]{47,48})\b'
HASH_REGEX = r'\b(0x[0-9a-fA-F]{64})\b'

def recognize_intent_rules(query: str) -> tuple[str, dict]:
    """
    Analyzes the query to determine intent and extract parameters using rule-based logic.
    (Content is the same as your previous intent_recognizer.py, moved here)
    Returns (intent_name, parameters_dict)
    """
    query_lower = query.lower()
    params = {}

    if "balance" in query_lower and ("account" in query_lower or "address" in query_lower):
        match = re.search(ADDRESS_REGEX, query)
        if match:
            params["address"] = match.group(1)
            return "get_balance", params
        else:
             return "unknown", {"reason": "Balance query detected, but no valid address found."}

    if ("extrinsic" in query_lower or "transaction" in query_lower) and "detail" in query_lower:
         match = re.search(HASH_REGEX, query)
         if match:
             params["hash"] = match.group(1)
             return "get_extrinsic", params
         else:
             return "unknown", {"reason": "Extrinsic query detected, but no valid hash found."}

    if "latest block" in query_lower or "current block" in query_lower:
        return "get_latest_block", params

    return "unknown", {"reason": "Query did not match any known rule-based patterns."}
