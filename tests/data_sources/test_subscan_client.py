# tests/test_subscan_client.py
import pytest
import httpx
import respx  # For mocking httpx requests

from polkaquery.data_sources.subscan_client import call_subscan_api
from fastapi import HTTPException

# Define constants for testing
MOCK_BASE_URL = "https://mock.subscan.io"
MOCK_API_KEY = "test_key_123"
MOCK_ADDRESS = "15oF4uVJwmo4TdGW7VfQxNLavjCXviqxT9S1MgbjMNHr6Sp5"
MOCK_HASH = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

# --- Mock Subscan Responses ---
# These should mimic the actual structure Subscan returns (check their docs!)

MOCK_BALANCE_RESPONSE_SUCCESS = {
    "code": 0,
    "message": "Success",
    "generated_at": 1678886400,
    "data": { # Assuming V1 structure for simplicity in mock
        "address": MOCK_ADDRESS,
        "balance": "12345000000000", # 1234.5 DOT (10 decimals)
        "locked": "1000000000000",
        # ... other fields
    }
    # V2 might return a list: "data": [{"address": MOCK_ADDRESS, "balance": "..."}]
}

MOCK_EXTRINSIC_RESPONSE_SUCCESS = {
    "code": 0,
    "message": "Success",
    "generated_at": 1678886401,
    "data": {
        "extrinsic_hash": MOCK_HASH,
        "block_num": 123456,
        "success": True,
        "call_module": "Balances",
        "call_module_function": "transfer",
        "fee": "12500000000", # 1.25 DOT
        # ... other fields
    }
}

MOCK_BLOCK_RESPONSE_SUCCESS = {
    "code": 0,
    "message": "Success",
    "generated_at": 1678886402,
    "data": {
        "count": 1,
        "blocks": [
            {
                "block_num": 987654,
                "block_timestamp": 1678886400,
                "extrinsics_count": 10,
                "event_count": 30,
                # ... other fields
            }
        ]
    }
}

MOCK_SUBSCAN_API_ERROR = {
    "code": 10001,
    "message": "Invalid Parameter",
    "generated_at": 1678886403,
    "data": None
}

# --- Test Fixture for Async Client ---
@pytest.fixture
async def async_client():
    """Provides an httpx.AsyncClient instance for tests."""
    async with httpx.AsyncClient() as client:
        yield client

# --- Tests ---
@pytest.mark.asyncio
@respx.mock
async def test_call_subscan_get_balance_success(async_client):
    """Tests successful call for get_balance intent."""
    # Define the expected request and mock response
    # IMPORTANT: Adjust path and method based on actual Subscan V2 endpoint!
    route = respx.post(f"{MOCK_BASE_URL}/api/v2/scan/accounts").mock( # Assuming V2 POST endpoint
        return_value=httpx.Response(200, json=MOCK_BALANCE_RESPONSE_SUCCESS)
    )

    params = {"address": MOCK_ADDRESS}
    result = await call_subscan_api(async_client, MOCK_BASE_URL, "get_balance", params, MOCK_API_KEY)

    # Assertions
    assert result == MOCK_BALANCE_RESPONSE_SUCCESS # Check if raw data is returned
    assert route.called
    last_request = route.calls.last.request
    assert last_request.method == "POST"
    assert last_request.headers.get("x-api-key") == MOCK_API_KEY
    assert last_request.content == b'{"address": "' + MOCK_ADDRESS.encode() + b'"}' # Check request body

@pytest.mark.asyncio
@respx.mock
async def test_call_subscan_get_extrinsic_success(async_client):
    """Tests successful call for get_extrinsic intent."""
    # IMPORTANT: Adjust path and method based on actual Subscan endpoint!
    route = respx.post(f"{MOCK_BASE_URL}/api/scan/extrinsic").mock( # Assuming V1 POST endpoint
        return_value=httpx.Response(200, json=MOCK_EXTRINSIC_RESPONSE_SUCCESS)
    )

    params = {"hash": MOCK_HASH}
    result = await call_subscan_api(async_client, MOCK_BASE_URL, "get_extrinsic", params, MOCK_API_KEY)

    assert result == MOCK_EXTRINSIC_RESPONSE_SUCCESS
    assert route.called
    last_request = route.calls.last.request
    assert last_request.method == "POST"
    assert last_request.headers.get("x-api-key") == MOCK_API_KEY
    assert last_request.content == b'{"hash": "' + MOCK_HASH.encode() + b'"}'

@pytest.mark.asyncio
@respx.mock
async def test_call_subscan_get_latest_block_success(async_client):
    """Tests successful call for get_latest_block intent."""
    # IMPORTANT: Adjust path and method based on actual Subscan endpoint!
    route = respx.post(f"{MOCK_BASE_URL}/api/scan/blocks").mock( # Assuming V1 POST endpoint
        return_value=httpx.Response(200, json=MOCK_BLOCK_RESPONSE_SUCCESS)
    )

    params = {} # No specific params needed
    result = await call_subscan_api(async_client, MOCK_BASE_URL, "get_latest_block", params, MOCK_API_KEY)

    assert result == MOCK_BLOCK_RESPONSE_SUCCESS
    assert route.called
    last_request = route.calls.last.request
    assert last_request.method == "POST"
    assert last_request.headers.get("x-api-key") == MOCK_API_KEY
    assert last_request.content == b'{"page": 0, "row": 1}' # Check request body for latest block

@pytest.mark.asyncio
@respx.mock
async def test_call_subscan_api_error(async_client):
    """Tests handling of Subscan API error (code != 0)."""
    route = respx.post(f"{MOCK_BASE_URL}/api/v2/scan/accounts").mock(
        return_value=httpx.Response(200, json=MOCK_SUBSCAN_API_ERROR) # API returns 200 OK but error in body
    )

    params = {"address": "invalid_address_format"}
    with pytest.raises(HTTPException) as exc_info:
        await call_subscan_api(async_client, MOCK_BASE_URL, "get_balance", params, MOCK_API_KEY)

    assert exc_info.value.status_code == 400
    assert MOCK_SUBSCAN_API_ERROR["message"] in exc_info.value.detail

@pytest.mark.asyncio
@respx.mock
async def test_call_subscan_http_error(async_client):
    """Tests handling of HTTP errors (e.g., 404, 500)."""
    route = respx.post(f"{MOCK_BASE_URL}/api/v2/scan/accounts").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    params = {"address": MOCK_ADDRESS}
    # The client raises httpx.HTTPStatusError, which should be caught by the main handler.
    # Here we test that the function *doesn't* suppress it or convert it incorrectly.
    with pytest.raises(httpx.HTTPStatusError):
         await call_subscan_api(async_client, MOCK_BASE_URL, "get_balance", params, MOCK_API_KEY)

@pytest.mark.asyncio
@respx.mock
async def test_call_subscan_network_error(async_client):
    """Tests handling of network errors."""
    route = respx.post(f"{MOCK_BASE_URL}/api/v2/scan/accounts").mock(
        side_effect=httpx.RequestError("Connection failed")
    )

    params = {"address": MOCK_ADDRESS}
    with pytest.raises(HTTPException) as exc_info:
        await call_subscan_api(async_client, MOCK_BASE_URL, "get_balance", params, MOCK_API_KEY)

    assert exc_info.value.status_code == 503
    assert "Network error calling Subscan API" in exc_info.value.detail

@pytest.mark.asyncio
async def test_call_subscan_missing_param(async_client):
    """Tests raising HTTPException if required params are missing before API call."""
    params = {} # Missing address
    with pytest.raises(HTTPException) as exc_info:
        await call_subscan_api(async_client, MOCK_BASE_URL, "get_balance", params, MOCK_API_KEY)
    assert exc_info.value.status_code == 400
    assert "Missing address parameter" in exc_info.value.detail

    params = {} # Missing hash
    with pytest.raises(HTTPException) as exc_info:
        await call_subscan_api(async_client, MOCK_BASE_URL, "get_extrinsic", params, MOCK_API_KEY)
    assert exc_info.value.status_code == 400
    assert "Missing hash parameter" in exc_info.value.detail

@pytest.mark.asyncio
async def test_call_subscan_unsupported_intent(async_client):
    """Tests raising HTTPException for an unsupported intent."""
    params = {}
    with pytest.raises(HTTPException) as exc_info:
        await call_subscan_api(async_client, MOCK_BASE_URL, "unsupported_intent", params, MOCK_API_KEY)
    assert exc_info.value.status_code == 400
    assert "Intent 'unsupported_intent' is not supported" in exc_info.value.detail

