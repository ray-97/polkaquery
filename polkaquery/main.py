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

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field

from polkaquery.config import settings
from polkaquery.core.resource_manager import ResourceManager
from polkaquery.core.network_config import DEFAULT_NETWORK

# --- Global Resource Manager ---
# This single instance will be used throughout the application's lifecycle.
# It holds the compiled LangGraph app and all necessary clients and resources.
resource_manager = ResourceManager(settings=settings)
# ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    print("INFO: Polkaquery application starting up...")
    await resource_manager.load_tools()
    # The graph is built in the ResourceManager constructor, so it's ready now.
    print(f"INFO: Tool loading complete. Subscan tools: {len(resource_manager.subscan_tools)}, AssetHub tools: {len(resource_manager.assethub_tools)}.")
    yield
    print("INFO: Polkaquery application shutting down...")
    await resource_manager.shutdown()

app = FastAPI(
    title="Polkaquery Agent",
    description="Polkadot ecosystem search agent powered by LangGraph.",
    version="0.9.0 (LangGraph)", 
    lifespan=lifespan 
)

# --- MCP Endpoint Models ---
class MCPQueryRequest(BaseModel):
    query: str
    network: str = Field(DEFAULT_NETWORK, description="Optional. The network to target.")

class MCPQueryResponse(BaseModel):
    answer: str

# --- Feedback Endpoint Models ---
class FeedbackModel(BaseModel):
    run_id: str = Field(..., description="The unique run ID from the /llm-query/ response.")
    score: int = Field(..., description="The feedback score, e.g., 1 for positive, 0 for negative.")
    key: str = Field("user-rating", description="The feedback key or category.")

@app.post("/feedback")
async def handle_feedback(feedback: FeedbackModel):
    """
    Receives user feedback and logs it to LangSmith.
    """
    langsmith_client = resource_manager.langsmith_client
    if not langsmith_client:
        raise HTTPException(
            status_code=503,
            detail="Feedback system is not configured. LANGCHAIN_API_KEY may be missing."
        )
    
    try:
        langsmith_client.create_feedback(
            run_id=feedback.run_id,
            key=feedback.key,
            score=feedback.score
        )
        return {"status": "success", "message": "Feedback received. Thank you!"}
    except Exception as e:
        print(f"ERROR [main.handle_feedback]: Could not submit feedback to LangSmith: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback.")

@app.post("/mcp/v1/query", response_model=MCPQueryResponse)
async def handle_mcp_query(request: MCPQueryRequest):
    """
    Handles a query compliant with the Multi-Chain Agent Protocol (MCP).
    """
    # The initial state for the graph
    initial_state = {
        "query": request.query,
        "network": request.network,
    }

    # The configuration for the run, passing the resource manager to all nodes
    config = {"configurable": {"resource_manager": resource_manager}}

    try:
        final_state = None
        # Asynchronously stream the graph execution to get the final state
        async for event in resource_manager.app.astream_events(initial_state, config=config, version="v1"):
            if event["event"] == "on_chain_end":
                final_state = event["data"]["output"]

        answer_node_output = final_state.get("generate_answer") or final_state.get("handle_error")

        if not answer_node_output or not answer_node_output.get("final_answer"):
            raise HTTPException(status_code=500, detail="Graph execution finished without a final answer.")

        return MCPQueryResponse(answer=answer_node_output.get("final_answer"))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during MCP query execution: {e}")

@app.post("/llm-query/")
async def handle_llm_query(query_body: dict = Body(...)):
    """
    Handles a natural language query by invoking the LangGraph agent.
    """
    raw_query = query_body.get("query")
    if not raw_query:
        raise HTTPException(status_code=400, detail="Query field is missing.")

    network = query_body.get("network", DEFAULT_NETWORK)

    # The initial state for the graph
    initial_state = {
        "query": raw_query,
        "network": network,
    }

    # The configuration for the run, passing the resource manager to all nodes
    config = {"configurable": {"resource_manager": resource_manager}}

    try:
        final_state = None
        run_id = None
        # Asynchronously stream the graph execution to get the final state
        async for event in resource_manager.app.astream_events(initial_state, config=config, version="v1"):
            # Capture the run_id from the first available event
            if run_id is None and event.get("run_id"):
                run_id = event.get("run_id")

            # The "on_chain_end" event contains the final output of the graph
            if event["event"] == "on_chain_end":
                final_state = event["data"]["output"]

        # The final state is a dictionary where keys are the names of the end nodes.
        # We need to get the output from one of the possible end nodes.
        answer_node_output = final_state.get("generate_answer") or final_state.get("handle_error")

        if not answer_node_output or not answer_node_output.get("final_answer"):
            print(f"ERROR [main]: Graph execution finished in an unexpected state: {final_state}")
            raise HTTPException(status_code=500, detail="Graph execution finished without a final answer.")

        # Return the final answer from the graph's state
        return {
            "answer": answer_node_output.get("final_answer"),
            "network": network,
            "run_id": run_id
        }

    except Exception as e:
        # This is a fallback for unexpected errors during the graph execution itself
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during graph execution: {e}")
