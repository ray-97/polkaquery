# tests/test_intent_recognizer.py
import pytest
from polkaquery.intent_recognizer import recognize_intent

# Define test cases: (query, expected_intent, expected_params_keys, expected_specific_param_value)
# The last element helps verify specific extracted values like address or hash.
test_data = [
    # Get Balance Tests
    ("what is the balance of address 15oF4uVJwmo4TdGW7VfQxNLavjCXviqxT9S1MgbjMNHr6Sp5?", "get_balance", ["address"], "15oF4uVJwmo4TdGW7VfQxNLavjCXviqxT9S1MgbjMNHr6Sp5"),
    ("show account balance for 15oF4uVJwmo4TdGW7VfQxNLavjCXviqxT9S1MgbjMNHr6Sp5", "get_balance", ["address"], "15oF4uVJwmo4TdGW7VfQxNLavjCXviqxT9S1MgbjMNHr6Sp5"),
    ("balance for 15oF4uVJwmo4TdGW7VfQxNLavjCXviqxT9S1MgbjMNHr6Sp5 please", "get_balance", ["address"], "15oF4uVJwmo4TdGW7VfQxNLavjCXviqxT9S1MgbjMNHr6Sp5"),
    ("balance of account?", "unknown", ["reason"], None), # Missing address
    ("what is the balance?", "unknown", ["reason"], None), # Missing address

    # Get Extrinsic Tests
    ("details for extrinsic 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef", "get_extrinsic", ["hash"], "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"),
    ("show me transaction details for 0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef12345678", "get_extrinsic", ["hash"], "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef12345678"),
    ("extrinsic details 0x1111111111111111111111111111111111111111111111111111111111111111", "get_extrinsic", ["hash"], "0x1111111111111111111111111111111111111111111111111111111111111111"),
    ("extrinsic details?", "unknown", ["reason"], None), # Missing hash
    ("transaction details", "unknown", ["reason"], None), # Missing hash

    # Get Latest Block Tests
    ("what is the latest block number?", "get_latest_block", [], None),
    ("current block", "get_latest_block", [], None),
    ("show latest block", "get_latest_block", [], None),

    # Unknown Intent Tests
    ("hello world", "unknown", ["reason"], None),
    ("how does staking work?", "unknown", ["reason"], None), # More complex query, not handled by rules
    ("", "unknown", ["reason"], None), # Empty query
]

@pytest.mark.parametrize("query, expected_intent, expected_params_keys, expected_specific_param_value", test_data)
def test_recognize_intent(query, expected_intent, expected_params_keys, expected_specific_param_value):
    """
    Tests the recognize_intent function with various queries.
    """
    intent, params = recognize_intent(query)

    # Check if the intent matches
    assert intent == expected_intent

    # Check if the expected parameter keys are present in the returned params dict
    assert all(key in params for key in expected_params_keys)

    # Check if the specific extracted value matches (if applicable)
    if expected_specific_param_value is not None:
        # Find the key corresponding to the specific value (e.g., 'address' or 'hash')
        value_key = next((k for k in expected_params_keys if k != 'reason'), None)
        if value_key:
            assert params.get(value_key) == expected_specific_param_value
