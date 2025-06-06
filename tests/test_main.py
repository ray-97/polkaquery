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

import pytest
import httpx
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock # For mocking async functions

# Ensure your main app can be imported.
# This might require adjusting PYTHONPATH or how you run pytest
# if 'polkaquery' is not directly in the path.
# Assuming pytest is run from project root and polkaquery is a package.
from polkaquery.main import app 

client = TestClient(app) # TestClient should handle lifespan automatically

# --- Mock Data ---
MOCK_SUBSCAN_RESPONSE = {"code": 0, "message": "Success", "data": {"balance": "10000000000"}}
MOCK_FORMATTED_SUBSCAN_DATA = {"summary": "Formatted Subscan Data", "key_data": {"balance": "1 DOT"}}
MOCK_INTERNET_SEARCH_RESPONSE = {"code": 0, "message": "Success", "data": {"results": [{"title": "Search Result"}]}}
MOCK_FORMATTED_INTERNET_DATA = {"summary": "Formatted Internet Search Data", "key_data": {"results_preview": [{"title": "Search Result"}]}}
MOCK_FINAL_LLM_ANSWER = "This is the final synthesized LLM answer."

@pytest.fixture
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("SUBSCAN_API_KEY", "fake_subscan_key")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "fake_gemini_key")
    monkeypatch.setenv("TAVILY_API_KEY", "fake_tavily_key")
    # Mock TavilyClient if it's used globally in main, or patch its instantiation
    monkeypatch.setattr("polkaquery.main.TavilyClient", MagicMock())
    monkeypatch.setattr("polkaquery.main.tavily_client", MagicMock())


def test_llm_query_endpoint_subscan_tool_flow(mock_env_vars): # Use the fixture
    with patch("polkaquery.main.recognize_intent_with_gemini_llm", AsyncMock(return_value=("account_balance", {"address": "1Test"}))) as mock_recognize, \
         patch("polkaquery.main.call_subscan_api", AsyncMock(return_value=MOCK_SUBSCAN_RESPONSE)) as mock_call_subscan, \
         patch("polkaquery.main.format_response_for_llm", MagicMock(return_value=MOCK_FORMATTED_SUBSCAN_DATA)) as mock_format, \
         patch("polkaquery.main.generate_final_llm_answer", AsyncMock(return_value=MOCK_FINAL_LLM_ANSWER)) as mock_generate_final:

        response = client.post("/llm-query/", json={"query": "balance of 1Test", "network": "polkadot"})

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == MOCK_FINAL_LLM_ANSWER
        assert data["debug_intent"] == "account_balance"
        
        mock_recognize.assert_called_once_with("balance of 1Test", "polkadot")
        mock_call_subscan.assert_called_once()
        mock_format.assert_called_once_with(
            intent_tool_name="account_balance",
            subscan_data=MOCK_SUBSCAN_RESPONSE,
            network_name="polkadot",
            decimals=10, # Assuming Polkadot from SUPPORTED_NETWORKS
            symbol="DOT", # Assuming Polkadot
            original_params={"address": "1Test"}
        )
        mock_generate_final.assert_called_once_with("balance of 1Test", "polkadot", MOCK_FORMATTED_SUBSCAN_DATA, "Subscan")

def test_llm_query_endpoint_internet_search_flow(mock_env_vars):
    with patch("polkaquery.main.recognize_intent_with_gemini_llm", AsyncMock(return_value=("internet_search", {"search_query": "polkadot news"}))) as mock_recognize, \
         patch("polkaquery.main.perform_internet_search", AsyncMock(return_value=MOCK_INTERNET_SEARCH_RESPONSE)) as mock_perform_search, \
         patch("polkaquery.main.format_response_for_llm", MagicMock(return_value=MOCK_FORMATTED_INTERNET_DATA)) as mock_format, \
         patch("polkaquery.main.generate_final_llm_answer", AsyncMock(return_value=MOCK_FINAL_LLM_ANSWER)) as mock_generate_final:

        response = client.post("/llm-query/", json={"query": "polkadot news", "network": "polkadot"})

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == MOCK_FINAL_LLM_ANSWER
        assert data["debug_intent"] == "internet_search"

        mock_recognize.assert_called_once_with("polkadot news", "polkadot")
        mock_perform_search.assert_called_once_with("polkadot news")
        mock_format.assert_called_once_with(
            intent_tool_name="internet_search",
            subscan_data=MOCK_INTERNET_SEARCH_RESPONSE,
            network_name="polkadot",
            decimals=0, symbol="", # For internet search
            original_params={"search_query": "polkadot news"}
        )
        mock_generate_final.assert_called_once_with("polkadot news", "polkadot", MOCK_FORMATTED_INTERNET_DATA, "InternetSearch")

def test_llm_query_endpoint_unknown_intent(mock_env_vars):
    with patch("polkaquery.main.recognize_intent_with_gemini_llm", AsyncMock(return_value=("unknown", {"reason": "Too vague"}))) as mock_recognize:
        response = client.post("/llm-query/", json={"query": "???", "network": "polkadot"})

        assert response.status_code == 200 # The endpoint itself handles this gracefully
        data = response.json()
        assert "Sorry, I couldn't process that request. Reason: Too vague" in data["answer"]
        mock_recognize.assert_called_once_with("???", "polkadot")

def test_llm_query_endpoint_unsupported_network(mock_env_vars):
    response = client.post("/llm-query/", json={"query": "balance", "network": "fakeNetwork"})
    assert response.status_code == 400 # Or as handled by your app's HTTPException
    assert "Unsupported network" in response.json()["detail"]


def test_llm_query_endpoint_subscan_api_http_error(mock_env_vars):
    with patch("polkaquery.main.recognize_intent_with_gemini_llm", AsyncMock(return_value=("account_balance", {"address": "1Test"}))) as mock_recognize, \
         patch("polkaquery.main.call_subscan_api", AsyncMock(side_effect=httpx.HTTPStatusError("API Error", request=MagicMock(), response=MagicMock(status_code=500, json=lambda: {"message": "Subscan down"})))) as mock_call_subscan:
        
        response = client.post("/llm-query/", json={"query": "balance of 1Test", "network": "polkadot"})
        
        assert response.status_code == 200 # Endpoint handles the error and returns 200 with error in "answer"
        data = response.json()
        assert "There was an issue fetching data" in data["answer"]
        assert "Status 500" in data["answer"]
        assert "Subscan down" in data["answer"]
        mock_recognize.assert_called_once()
        mock_call_subscan.assert_called_once()

