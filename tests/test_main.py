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
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import uuid

from polkaquery.main import app

# This client will be used in all tests
client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_env_and_dependencies(monkeypatch):
    """
    Auto-applied fixture to set environment variables and mock all external clients
    to prevent real network calls during tests.
    """
    monkeypatch.setenv("SUBSCAN_API_KEY", "fake_subscan_key")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "fake_gemini_key")
    monkeypatch.setenv("TAVILY_API_KEY", "fake_tavily_key")
    monkeypatch.setenv("ONFINALITY_API_KEY", "fake_onfinality_key")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "fake_langsmith_key")

    # Patch the client classes within the module where they are instantiated
    monkeypatch.setattr("polkaquery.core.resource_manager.httpx.AsyncClient", MagicMock())
    monkeypatch.setattr("polkaquery.core.resource_manager.genai.GenerativeModel", MagicMock())
    monkeypatch.setattr("polkaquery.core.resource_manager.TavilyClient", MagicMock())
    monkeypatch.setattr("polkaquery.core.resource_manager.SubstrateInterface", MagicMock())
    monkeypatch.setattr("polkaquery.core.resource_manager.LangSmithClient", MagicMock())

def test_health_check_endpoint():
    """Tests the /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_llm_query_endpoint_success_flow():
    """Tests a successful end-to-end flow of the /llm-query/ endpoint by mocking the graph stream."""
    mock_run_id = uuid.uuid4()
    mock_final_state = {"generate_answer": {"final_answer": "The balance is 100 DOT."}}
    
    # Mock the event stream from LangGraph
    async def mock_astream_events(*args, **kwargs):
        yield {"event": "on_chain_start", "run_id": mock_run_id}
        yield {"event": "on_chain_end", "data": {"output": mock_final_state}}

    with patch("polkaquery.main.resource_manager.app.astream_events", new=mock_astream_events):
        response = client.post("/llm-query/", json={"query": "test query", "network": "polkadot"})

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["answer"] == "The balance is 100 DOT."
    assert response_data["run_id"] == str(mock_run_id)

@pytest.mark.asyncio
async def test_llm_query_endpoint_graph_error_flow():
    """Tests the flow where the graph execution results in an error node."""
    mock_run_id = uuid.uuid4()
    mock_final_state_with_error = {"handle_error": {"final_answer": "Sorry, an error occurred."}}
    
    async def mock_astream_events(*args, **kwargs):
        yield {"event": "on_chain_start", "run_id": mock_run_id}
        yield {"event": "on_chain_end", "data": {"output": mock_final_state_with_error}}

    with patch("polkaquery.main.resource_manager.app.astream_events", new=mock_astream_events):
        response = client.post("/llm-query/", json={"query": "error query"})

    assert response.status_code == 200
    assert response.json()["answer"] == "Sorry, an error occurred."

def test_llm_query_missing_query_field():
    """Tests that a 400 error is returned if the query field is missing."""
    response = client.post("/llm-query/", json={"network": "polkadot"})
    assert response.status_code == 400
    assert response.json() == {"detail": "Query field is missing."}
