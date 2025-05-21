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
from unittest.mock import patch, MagicMock # For mocking TavilyClient

# The function to test is in main.py
from polkaquery.main import perform_internet_search 

@pytest.mark.asyncio
async def test_perform_internet_search_with_tavily_success(monkeypatch):
    search_query = "latest Polkadot updates"
    mock_tavily_response = {
        "query": search_query,
        "answer": "Polkadot 2.0 is upcoming with new features.",
        "results": [
            {"title": "Polkadot 2.0 News", "url": "http://example.com/news1", "content": "Details about Polkadot 2.0..."},
            {"title": "Polkadot Staking Changes", "url": "http://example.com/staking", "content": "Updates to staking..."}
        ]
    }

    # Mock the TavilyClient instance and its search method
    mock_tavily_client_instance = MagicMock()
    mock_tavily_client_instance.search = MagicMock(return_value=mock_tavily_response)

    # Patch the tavily_client global in main.py
    monkeypatch.setattr("polkaquery.main.tavily_client", mock_tavily_client_instance)
    # Ensure TAVILY_API_KEY is perceived as set for this test path
    monkeypatch.setenv("TAVILY_API_KEY", "fake_tavily_key")


    result = await perform_internet_search(search_query)

    assert result["code"] == 0
    assert result["message"] == "Tavily search successful"
    assert result["data"]["search_provider"] == "Tavily"
    assert result["data"]["query_used"] == search_query
    assert result["data"]["answer_summary"] == "Polkadot 2.0 is upcoming with new features."
    assert len(result["data"]["results"]) == 2
    assert result["data"]["results"][0]["title"] == "Polkadot 2.0 News"
    mock_tavily_client_instance.search.assert_called_once_with(query=search_query, search_depth="advanced", max_results=3, include_answer=True)

@pytest.mark.asyncio
async def test_perform_internet_search_tavily_api_error(monkeypatch):
    search_query = "another search"
    
    mock_tavily_client_instance = MagicMock()
    mock_tavily_client_instance.search = MagicMock(side_effect=Exception("Tavily API Error"))

    monkeypatch.setattr("polkaquery.main.tavily_client", mock_tavily_client_instance)
    monkeypatch.setenv("TAVILY_API_KEY", "fake_tavily_key")

    result = await perform_internet_search(search_query)

    assert result["code"] == -1
    assert "Internet search with Tavily failed: Tavily API Error" in result["message"]
    assert result["data"] is None

@pytest.mark.asyncio
async def test_perform_internet_search_no_tavily_client(monkeypatch):
    search_query = "search without tavily"
    
    # Ensure tavily_client is None in main.py for this test
    monkeypatch.setattr("polkaquery.main.tavily_client", None)
    # Also simulate TAVILY_API_KEY not being set or client not imported
    monkeypatch.setenv("TAVILY_API_KEY", "") 
    monkeypatch.setattr("polkaquery.main.TavilyClient", None) # Simulate import failure


    result = await perform_internet_search(search_query)

    assert result["code"] == 0
    assert result["message"] == "Placeholder Internet Search"
    assert result["data"]["search_provider"] == "Placeholder"
    assert result["data"]["query_used"] == search_query
    assert "placeholder search result" in result["data"]["results"][0]["content"].lower() # Check lowercase

@pytest.mark.asyncio
async def test_perform_internet_search_no_tavily_api_key(monkeypatch):
    search_query = "search with tavily lib but no key"
    
    monkeypatch.setattr("polkaquery.main.tavily_client", None) 
    monkeypatch.setenv("TAVILY_API_KEY", "") 
    monkeypatch.setattr("polkaquery.main.TavilyClient", MagicMock())

    result = await perform_internet_search(search_query)

    assert result["code"] == 0
    assert result["message"] == "Placeholder Internet Search"
    
    # Make assertions case-insensitive to be more robust
    content_lower = result["data"]["results"][0]["content"].lower()
    assert "placeholder search result" in content_lower
    assert "tavily client is not configured" in content_lower

