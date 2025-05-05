# main.py
import os
from fastapi import FastAPI, HTTPException, Body
from dotenv import load_dotenv
import httpx

# Load environment variables (e.g., for API keys)
load_dotenv()
SUBSCAN_API_KEY = os.getenv("SUBSCAN_API_KEY")

# Import our custom modules
from polkaquery.intent_recognizer import recognize_intent
from polkaquery.subscan_client import call_subscan_api
from polkaquery.formatter import format_response

app = FastAPI(
    title="Polkaquery",
    description="A Web3 search engine for the Polkadot ecosystem.",
    version="0.1.0 (MVP)"
)

# Create a single httpx client for reuse
# todo: Consider adding timeout configurations
http_client = httpx.AsyncClient()

@app.on_event("startup")
async def startup_event():
    # You can initialize resources here if needed
    pass

@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose() # Close the client when app shuts down

@app.post("/query/")
async def handle_query(query_body: dict = Body(...)):
    """
    Accepts a natural language query about the Polkadot ecosystem
    and attempts to answer it.
    """
    raw_query = query_body.get("query")
    if not raw_query:
        raise HTTPException(status_code=400, detail="Query field is missing.")

    try:
        # 1. Recognize Intent
        intent, params = recognize_intent(raw_query)

        if intent == "unknown":
            raise HTTPException(status_code=400, detail="Could not understand the query or missing required parameters.")

        # 2. Call Subscan API based on intent
        # The base URL might vary depending on the specific Polkadot/Kusama/Parachain network
        # We'll need to configure this, potentially based on the query or a default
        subscan_base_url = "https://polkadot.api.subscan.io" # Example for Polkadot Mainnet

        subscan_response_json = await call_subscan_api(
            client=http_client,
            base_url=subscan_base_url,
            intent=intent,
            params=params,
            api_key=SUBSCAN_API_KEY
        )

        # 3. Format the response
        formatted_result = format_response(intent, subscan_response_json)

        return {"answer": formatted_result}

    except httpx.HTTPStatusError as e:
        # Handle errors specifically from Subscan or network issues
        raise HTTPException(status_code=e.response.status_code, detail=f"Error calling Subscan API: {e.response.text}")
    except HTTPException as e:
        # Re-raise exceptions we've already shaped
        raise e
    except Exception as e:
        # Catch-all for unexpected errors during processing
        print(f"Unexpected error: {e}") # Log the full error for debugging
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

# Add command to run the server: uvicorn main:app --reload