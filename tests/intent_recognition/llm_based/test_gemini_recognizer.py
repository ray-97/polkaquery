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
import json
from unittest.mock import AsyncMock, MagicMock
# Import the cache object to clear it in tests
from polkaquery.intent_recognition.llm_based.gemini_recognizer import recognize_intent_with_gemini_llm, llm_cache

# Sample data for testing
SAMPLE_TOOLS = [
    {
        "name": "get_balance",
        "description": "Get the balance of a given account address.",
        "parameters": {
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "The account address."}
            },
            "required": ["address"]
        }
    },
    {
        "name": "internet_search",
        "description": "Performs an internet search for a given query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."}
            },
            "required": ["query"]
        }
    }
]

SAMPLE_PROMPT_TEMPLATE = "Please choose a tool based on the user query."

@pytest.fixture
def mock_gemini_model():
    """Provides a mock Gemini GenerativeModel for tests."""
    model = MagicMock()
    model.generate_content_async = AsyncMock()
    return model

@pytest.fixture(autouse=True)
def clear_cache_before_test():
    """Fixture to automatically clear the cache before each test run."""
    llm_cache.clear()

@pytest.mark.asyncio
async def test_recognize_intent_success(mock_gemini_model):
    """Tests successful recognition of a tool and its parameters."""
    user_query = "What is the balance of address 12345?"
    mock_llm_response = {"intent": "get_balance", "parameters": {"address": "12345"}}
    
    mock_response_obj = MagicMock()
    mock_response_obj.text = json.dumps(mock_llm_response)
    mock_gemini_model.generate_content_async.return_value = mock_response_obj

    intent, params = await recognize_intent_with_gemini_llm(
        user_query, mock_gemini_model, SAMPLE_TOOLS, SAMPLE_PROMPT_TEMPLATE
    )

    assert intent == "get_balance"
    assert params == {"address": "12345"}

@pytest.mark.asyncio
async def test_recognize_intent_unknown_tool(mock_gemini_model):
    """Tests handling of a response where the LLM chooses a non-existent tool."""
    user_query = "some query for unknown tool"
    mock_llm_response = {"intent": "non_existent_tool", "parameters": {}}
    mock_response_obj = MagicMock()
    mock_response_obj.text = json.dumps(mock_llm_response)
    mock_gemini_model.generate_content_async.return_value = mock_response_obj

    intent, params = await recognize_intent_with_gemini_llm(
        user_query, mock_gemini_model, SAMPLE_TOOLS, SAMPLE_PROMPT_TEMPLATE
    )

    assert intent == "unknown"
    assert "LLM chose a non-existent tool" in params["reason"]

@pytest.mark.asyncio
async def test_recognize_intent_invalid_json(mock_gemini_model):
    """Tests handling of a response with invalid JSON."""
    user_query = "some query for invalid json"
    mock_response_obj = MagicMock()
    mock_response_obj.text = "this is not valid json"
    mock_gemini_model.generate_content_async.return_value = mock_response_obj

    intent, params = await recognize_intent_with_gemini_llm(
        user_query, mock_gemini_model, SAMPLE_TOOLS, SAMPLE_PROMPT_TEMPLATE
    )

    assert intent == "unknown"
    assert "was not valid JSON" in params["reason"]

@pytest.mark.asyncio
async def test_recognize_intent_missing_required_param(mock_gemini_model):
    """Tests that the function correctly identifies when a required parameter is missing."""
    user_query = "Get the balance"
    mock_llm_response = {"intent": "get_balance", "parameters": {}}
    mock_response_obj = MagicMock()
    mock_response_obj.text = json.dumps(mock_llm_response)
    mock_gemini_model.generate_content_async.return_value = mock_response_obj

    intent, params = await recognize_intent_with_gemini_llm(
        user_query, mock_gemini_model, SAMPLE_TOOLS, SAMPLE_PROMPT_TEMPLATE
    )

    assert intent == "unknown"
    # Corrected assertion to match the actual, more detailed error message
    assert "did not extract required parameters" in params["reason"]
    assert "address" in params["reason"]
