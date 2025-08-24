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
from unittest.mock import MagicMock

from polkaquery.core.helpers import perform_internet_search
from polkaquery.core.resource_manager import ResourceManager

@pytest.fixture
def mock_resource_manager():
    """Provides a mock ResourceManager instance for tests."""
    rm = MagicMock(spec=ResourceManager)
    rm.tavily_client = None
    return rm

@pytest.mark.asyncio
async def test_perform_internet_search_with_tavily_success(mock_resource_manager):
    search_query = "latest Polkadot updates"
    mock_tavily_response = {
        "query": search_query,
        "answer": "Polkadot 2.0 is upcoming with new features.",
        "results": [
            {"title": "Polkadot 2.0 News", "url": "http://example.com/news1", "content": "Details about Polkadot 2.0..."}
        ]
    }

    mock_tavily_client = MagicMock()
    # The search method is synchronous, so we use MagicMock, not AsyncMock
    mock_tavily_client.search = MagicMock(return_value=mock_tavily_response)
    mock_resource_manager.tavily_client = mock_tavily_client

    result = await perform_internet_search(mock_resource_manager, search_query)

    assert result["code"] == 0
    assert result["message"] == "Tavily search successful"
    assert result["data"]["answer_summary"] == "Polkadot 2.0 is upcoming with new features."
    mock_tavily_client.search.assert_called_once_with(query=search_query, search_depth="advanced", max_results=3, include_answer=True)

@pytest.mark.asyncio
async def test_perform_internet_search_tavily_api_error(mock_resource_manager):
    search_query = "another search"
    
    mock_tavily_client = MagicMock()
    # The search method is synchronous, so we use MagicMock for the side_effect
    mock_tavily_client.search = MagicMock(side_effect=Exception("Tavily API Error"))
    mock_resource_manager.tavily_client = mock_tavily_client

    result = await perform_internet_search(mock_resource_manager, search_query)

    assert result["code"] == -1
    assert "Internet search with Tavily failed: Tavily API Error" in result["message"]

@pytest.mark.asyncio
async def test_perform_internet_search_no_tavily_client(mock_resource_manager):
    search_query = "search without tavily"
    
    # Fixture provides rm with tavily_client = None
    result = await perform_internet_search(mock_resource_manager, search_query)

    assert result["code"] == 0
    assert result["message"] == "Placeholder Internet Search"
    # Corrected assertion to match the actual placeholder content
    assert "tavily client is not configured" in result["data"]["results"][0]["content"].lower()
