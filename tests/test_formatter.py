# tests/test_formatter.py
import pytest
from polkaquery.formatter import format_response, format_planck

# Use mock responses defined in test_subscan_client or define similar ones here
# For simplicity, let's reuse the structures (assuming they are imported or redefined)
# Re-defining mock data here for clarity and independence of test files
MOCK_ADDRESS = "15oF4uVJwmo4TdGW7VfQxNLavjCXviqxT9S1MgbjMNHr6Sp5"
MOCK_HASH = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
POLKADOT_DECIMALS = 10

MOCK_BALANCE_DATA_V1_STYLE = { # V1 style data field
    "address": MOCK_ADDRESS,
    "balance": "12345000000000", # 1234.5 DOT
    "locked": "1000000000000",
}
MOCK_BALANCE_RESPONSE_SUCCESS_V1 = {"code": 0, "message": "Success", "data": MOCK_BALANCE_DATA_V1_STYLE}

# Example V2 style response (list) - Adapt formatter if needed!
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
        }
    ]
}
MOCK_BLOCK_RESPONSE_SUCCESS = {"code": 0, "message": "Success", "data": MOCK_BLOCK_DATA}

MOCK_EMPTY_DATA_RESPONSE = {"code": 0, "message": "Success", "data": None}
MOCK_UNEXPECTED_DATA_RESPONSE = {"code": 0, "message": "Success", "data": {"unexpected_field": "value"}}

# --- format_planck Tests ---
@pytest.mark.parametrize("value_str, decimals, expected", [
    ("12345000000000", 10, "1,234.5"),
    ("10000000000", 10, "1"),
    ("500000000", 10, "0.05"),
    ("0", 10, "0"),
    ("12345678901234567890", 10, "1,234,567,890.123456789"), # Large number
    (None, 10, "N/A"),
    ("", 10, "N/A"),
    ("not a number", 10, "Invalid Format"),
    ("1000000000000", 12, "1"), # Test different decimals (KSM)
])
def test_format_planck(value_str, decimals, expected):
    """Tests the format_planck helper function."""
    assert format_planck(value_str, decimals) == expected

# --- format_response Tests ---
def test_format_response_get_balance_v1():
    """Tests formatting for get_balance intent (V1 style data)."""
    result = format_response("get_balance", MOCK_BALANCE_RESPONSE_SUCCESS_V1)
    assert f"balance of address {MOCK_ADDRESS}" in result
    assert "1,234.5 DOT" in result # Check formatted balance

def test_format_response_get_balance_v2():
    """Tests formatting for get_balance intent (V2 style data)."""
    # NOTE: Current formatter might need adjustment for V2 list format.
    # Assuming the formatter handles the list correctly (takes first item):
    result = format_response("get_balance", MOCK_BALANCE_RESPONSE_SUCCESS_V2)
    assert f"balance of address {MOCK_ADDRESS}" in result
    assert "9,876 DOT" in result # Check formatted balance

def test_format_response_get_extrinsic_success():
    """Tests formatting for successful get_extrinsic intent."""
    result = format_response("get_extrinsic", MOCK_EXTRINSIC_RESPONSE_SUCCESS)
    assert f"Extrinsic {MOCK_HASH}" in result
    assert "block 123456" in result
    assert "was successful" in result
    assert "Balances.transfer" in result
    assert "fee of 1.25 DOT" in result

def test_format_response_get_extrinsic_failed():
    """Tests formatting for failed get_extrinsic intent."""
    result = format_response("get_extrinsic", MOCK_EXTRINSIC_RESPONSE_FAILED)
    assert f"Extrinsic {MOCK_HASH}" in result
    assert "block 123456" in result
    assert "was failed" in result # Check status word
    assert "Balances.transfer" in result
    assert "fee of 1.25 DOT" in result

def test_format_response_get_latest_block():
    """Tests formatting for get_latest_block intent."""
    result = format_response("get_latest_block", MOCK_BLOCK_RESPONSE_SUCCESS)
    assert "latest finalized block is #987654" in result
    assert "10 extrinsics" in result
    assert "30 events" in result

def test_format_response_empty_data():
    """Tests formatting when Subscan returns success code but null data."""
    result = format_response("get_balance", MOCK_EMPTY_DATA_RESPONSE)
    assert "no data found for intent 'get_balance'" in result

def test_format_response_unexpected_data():
    """Tests formatting handles unexpected data structure gracefully."""
    # This tests the outer try/except in format_response
    result = format_response("get_balance", MOCK_UNEXPECTED_DATA_RESPONSE)
    assert "Error processing the data received from Subscan" in result

def test_format_response_unimplemented_intent():
    """Tests the fallback for unimplemented intents."""
    result = format_response("unimplemented_intent", {"code": 0, "data": {}})
    assert "Formatting not implemented for intent 'unimplemented_intent'" in result

