# Polkaquery
# Copyright (C) 2025 Polkaquery_Team
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

import pytest
# Updated import path
from polkaquery.core.formatter import format_response, format_planck

# --- Mock Data (copied from previous test_formatter.py for self-containment) ---
MOCK_ADDRESS = "15oF4uVJwmo4TdGW7VfQxNLavjCXviqxT9S1MgbjMNHr6Sp5"
MOCK_HASH = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
POLKADOT_DECIMALS = 10
POLKADOT_SYMBOL = "DOT"
KUSAMA_DECIMALS = 12
KUSAMA_SYMBOL = "KSM"

MOCK_BALANCE_DATA_V1_STYLE = {
    "address": MOCK_ADDRESS,
    "balance": "12345000000000", # 1234.5 DOT
}
MOCK_BALANCE_RESPONSE_SUCCESS_V1 = {"code": 0, "message": "Success", "data": MOCK_BALANCE_DATA_V1_STYLE}

MOCK_BALANCE_DATA_V2_STYLE = [
     {"address": MOCK_ADDRESS, "balance": "98760000000000"} # 9876 DOT
]
MOCK_BALANCE_RESPONSE_SUCCESS_V2 = {"code": 0, "message": "Success", "data": MOCK_BALANCE_DATA_V2_STYLE}


MOCK_EXTRINSIC_DATA = {
    "extrinsic_hash": MOCK_HASH,
    "block_num": 123456,
    "success": True,
    "call_module": "Balances",
    "call_module_function": "transfer",
    "fee": "12500000000", # 1.25 DOT
    "block_timestamp": 1678886401,
    "account_id": "1SenderAddress"
}
MOCK_EXTRINSIC_RESPONSE_SUCCESS = {"code": 0, "message": "Success", "data": MOCK_EXTRINSIC_DATA}
MOCK_EXTRINSIC_RESPONSE_FAILED = {"code": 0, "message": "Success", "data": {**MOCK_EXTRINSIC_DATA, "success": False}}


MOCK_BLOCK_DATA = {
    "count": 1,
    "blocks": [
        {
            "block_num": 987654,
            "block_timestamp": 1678886400,
            "extrinsics_count": 10,
            "event_count": 30,
            "validator_name": "SuperValidator"
        }
    ]
}
MOCK_BLOCK_RESPONSE_SUCCESS = {"code": 0, "message": "Success", "data": MOCK_BLOCK_DATA}

MOCK_EMPTY_DATA_RESPONSE = {"code": 0, "message": "Success", "data": None}
MOCK_ERROR_CODE_RESPONSE = {"code": 10001, "message": "Specific Subscan Error", "data": None}
MOCK_UNEXPECTED_DATA_RESPONSE = {"code": 0, "message": "Success", "data": {"unexpected_field": "value"}}
# --- End Mock Data ---

# --- format_planck Tests ---
@pytest.mark.parametrize("value_str, decimals, expected", [
    ("12345000000000", 10, "1,234.5"),
    ("10000000000", 10, "1"),
    ("500000000", 10, "0.05"),
    ("0", 10, "0"),
    ("12345678901234567890", 10, "1,234,567,890.123456789"),
    (None, 10, "N/A"),
    ("", 10, "N/A"),
    ("not a number", 10, "Invalid Format"),
    ("1000000000000", 12, "1"),
    ("1", 0, "1"), # Test with 0 decimals
    ("123", -1, "123"), # Test with negative decimals (should return original)
])
def test_format_planck(value_str, decimals, expected):
    assert format_planck(value_str, decimals) == expected

# --- format_response Tests ---
def test_format_response_get_balance_v1_polkadot():
    result = format_response(
        "get_balance",
        MOCK_BALANCE_RESPONSE_SUCCESS_V1,
        "polkadot",
        POLKADOT_DECIMALS,
        POLKADOT_SYMBOL,
        params={"address": MOCK_ADDRESS}
    )
    assert f"Account {MOCK_ADDRESS} on polkadot:" in result
    assert f"- Total Balance: 1,234.5 {POLKADOT_SYMBOL}" in result

def test_format_response_get_balance_v2_kusama():
    result = format_response(
        "get_balance",
        MOCK_BALANCE_RESPONSE_SUCCESS_V2,
        "kusama",
        KUSAMA_DECIMALS,
        KUSAMA_SYMBOL,
        params={"address": MOCK_ADDRESS}
    )
    assert f"Account {MOCK_ADDRESS} on kusama:" in result
    assert f"- Total Balance: 9,876 {KUSAMA_SYMBOL}" in result # 98760000000000 / 10^12

def test_format_response_get_extrinsic_success():
    result = format_response(
        "get_extrinsic",
        MOCK_EXTRINSIC_RESPONSE_SUCCESS,
        "polkadot",
        POLKADOT_DECIMALS,
        POLKADOT_SYMBOL,
        params={"hash": MOCK_HASH}
    )
    assert f"Extrinsic {MOCK_HASH} on polkadot:" in result
    assert "Block: 123456" in result
    assert "Signer: 1SenderAddress" in result
    assert "Call: Balances.transfer" in result
    assert "Status: successful" in result
    assert f"Fee: 1.25 {POLKADOT_SYMBOL}" in result # 12500000000 / 10^10
    assert "2023-03-15" in result # Check for timestamp presence

def test_format_response_get_extrinsic_failed():
    result = format_response(
        "get_extrinsic",
        MOCK_EXTRINSIC_RESPONSE_FAILED,
        "polkadot",
        POLKADOT_DECIMALS,
        POLKADOT_SYMBOL,
        params={"hash": MOCK_HASH}
    )
    assert "Status: failed" in result

def test_format_response_get_latest_block():
    result = format_response(
        "get_latest_block",
        MOCK_BLOCK_RESPONSE_SUCCESS,
        "westend",
        12, # Westend decimals
        "WND",
        params={}
    )
    assert "Latest finalized block on westend is #987654" in result
    assert "10 extrinsics and 30 events" in result
    assert "Produced by validator: SuperValidator" in result
    assert "2023-03-15" in result # Check for timestamp presence

def test_format_response_empty_data():
    result = format_response("get_balance", MOCK_EMPTY_DATA_RESPONSE, "polkadot", 10, "DOT")
    assert "Subscan reported success, but no specific data was found" in result

def test_format_response_error_code_from_subscan():
    result = format_response("get_balance", MOCK_ERROR_CODE_RESPONSE, "polkadot", 10, "DOT")
    assert "Received error code 10001 from Subscan on polkadot: Specific Subscan Error" in result


def test_format_response_unexpected_data_structure():
    result = format_response("get_balance", MOCK_UNEXPECTED_DATA_RESPONSE, "polkadot", 10, "DOT", params={"address": "testaddr"})
    # This tests the outer try/except in format_response, which catches parsing errors
    assert "Error processing the data received from Subscan" in result

def test_format_response_unimplemented_intent():
    result = format_response("some_new_intent", {"code": 0, "data": {}}, "polkadot", 10, "DOT")
    assert "Formatting not implemented for intent 'some_new_intent'" in result

def test_format_response_balance_no_account_info():
    """Tests when 'data' is present but account_info cannot be derived (e.g., empty list or wrong dict)."""
    empty_list_data = {"code": 0, "message": "Success", "data": []}
    result = format_response("get_balance", empty_list_data, "polkadot", 10, "DOT", params={"address": "testaddr"})
    assert "Could not parse balance information for the requested address (testaddr) on polkadot." in result

    wrong_dict_data = {"code": 0, "message": "Success", "data": {"info": "not_account_data"}}
    result = format_response("get_balance", wrong_dict_data, "polkadot", 10, "DOT", params={"address": "testaddr"})
    assert "Could not parse balance information for the requested address (testaddr) on polkadot." in result
