# Polkaquery: A Web3 Search Engine for the Polkadot Ecosystem

**Version:** 0.7.1 (Updated README)
**License:** [GNU General Public License v3.0](LICENSE)

## Table of Contents

1.  [Project Description](#project-description)
2.  [Features](#features)
3.  [Setup and Installation](#setup-and-installation)
    * [Prerequisites](#prerequisites)
    * [Environment Setup](#environment-setup)
    * [API Keys](#api-keys)
4.  [Running Polkaquery Components](#running-polkaquery-components)
    * [Step 1: Automated Tool Generation](#step-1-automated-tool-generation)
    * [Step 2: Run the Polkaquery FastAPI Server](#step-2-run-the-polkaquery-fastapi-server)
    * [Step 3: Run Integration Examples](#step-3-run-integration-examples)
5.  [Interpreting Outcomes & Examples](#interpreting-outcomes--examples)
6.  [Agent Integrations](#agent-integrations)
    * [MCP (Multi-Chain Agent Protocol) Integration](#mcp-multi-chain-agent-protocol-integration)
7.  [Future Enhancements (Roadmap Ideas)](#future-enhancements-roadmap-ideas)
8.  [Contributing](#contributing)
9.  [License](#license)

---

## Project Description

Polkaquery is a specialized search engine designed for the Polkadot ecosystem. It acts as an intelligent interface between AI agents (built with frameworks like Langchain or interacting with LLMs like those served by Ollama) and Polkadot's on-chain data. Instead of traditional web crawling, Polkaquery translates natural language queries into specific API calls to data sources like Subscan, retrieves the information, and provides a synthesized answer.

The primary goal is to enable AI agents to easily access and understand Polkadot blockchain data, functioning similarly to how tools like Tavily Search provide general web search capabilities to agents. This project aims to fulfill the deliverables outlined in the Web3 Foundation Founders Software Grant Agreement, focusing on creating data loaders and function tools for LLM interaction with on-chain data.

##### Architecture Overview
Polkaquery now features a sophisticated dual-client architecture to provide comprehensive data from the Polkadot ecosystem.
1. Subscan Client: The primary client for a broad range of on-chain data across multiple networks supported by Subscan's powerful APIs. This is used for queries related to blocks, extrinsics, staking, and general account information on most parachains.

2. AssetHub RPC Client: A specialized client that connects directly to an AssetHub node's WebSocket endpoint (via OnFinality). This provides deep, specific access to the Assets and Uniques pallets, allowing for detailed queries about fungible tokens and NFTs that are not available through the general Subscan API.

##### Automatic Routing
When a query is received, Polkaquery uses a keyword-based routing mechanism:
- If the query contains terms like assethub, statemint, or statemine, it is automatically routed to the AssetHub RPC Client.
- If the user explicitly includes the word subscan in their query, it will be forced to use the Subscan Client.
- Otherwise, the query defaults to using the general-purpose Subscan Client.
This architecture allows Polkaquery to use the best tool for the job, combining the breadth of Subscan with the depth of direct RPC access.


## Features

* **LLM-Powered Intent Recognition:** Uses Google Gemini to understand natural language queries and select the appropriate data-fetching tool.
* **Subscan API Integration:** Dynamically generates tool definitions for a wide range of Subscan API endpoints.
* **Internet Search Fallback:** Integrates Tavily for general web searches when queries are broad or not covered by specific on-chain data tools.
* **FastAPI Backend:** A robust and efficient backend service to handle queries.
* **Langchain Integration Example:** Demonstrates how to use Polkaquery as a tool within a Langchain agent using Google Gemini.
* **Ollama Integration Example:** Shows how to interact with Polkaquery using a locally hosted LLM via Ollama.
* **Modular Design:** Code is structured for better maintainability and scalability.

## Setup and Installation

### Prerequisites

* Python 3.10+
* Access to Google Gemini API (requires an API key)
* Tavily API key (for internet search functionality)
* Subscan API key (recommended for reliable Subscan data access)
* (Optional for Ollama integration) Ollama installed and a model pulled (e.g., `phi3:mini`, `llama3`)

### Environment Setup

1.  **Clone the repository (if applicable):**
    ```bash
    # git clone <repository_url>
    # cd polkaquery_project_root
    ```

2.  **Create and activate a Python virtual environment:**
    * Using `venv`:
        ```bash
        python3 -m venv .venv
        source .venv/bin/activate
        ```
    * Using `uv` (if installed):
        ```bash
        uv venv
        source .venv/bin/activate
        ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    # or using uv
    # uv pip install -r requirements.txt
    ```
    Ensure `requirements.txt` includes: `fastapi uvicorn python-dotenv httpx PyYAML beautifulsoup4 requests langchain langchain-google-genai langchain-ollama pydantic tavily-python ollama` (adjust as needed).

### API Keys

1.  Create a `.env` file in the project root (`polkaquery_project_root/`) by copying `.env.example` or creating a new one.
2.  Add your API keys to the `.env` file.

    ```env
    # --- Core Service Keys (Required for full functionality) ---
    SUBSCAN_API_KEY=YOUR_SUBSCAN_API_KEY_HERE
    GOOGLE_GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE
    TAVILY_API_KEY=YOUR_TAVILY_API_KEY_HERE
    ONFINALITY_API_KEY=ONFINALITY_API_KEY_HERE

    # --- LangSmith Tracing (Optional, for debugging and monitoring) ---
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=YOUR_LANGSMITH_API_KEY_HERE
    LANGCHAIN_PROJECT=YOUR_PROJECT_NAME_HERE # e.g., Polkaquery-Dev

    # --- Ollama Integration (Optional) ---
    # OLLAMA_BASE_URL=http://localhost:11434
    # OLLAMA_MODEL=phi3:mini
    ```
    *   **Core Service Keys**: `GOOGLE_GEMINI_API_KEY`, `TAVILY_API_KEY`, `SUBSCAN_API_KEY`, and `ONFINALITY_API_KEY` are essential for the main features to work correctly.
    *   **LangSmith Tracing**: If you want to debug, trace, and monitor the internal workings of the LangGraph agent, you need to set up a [LangSmith](https://www.langchain.com/langsmith) account and provide the corresponding API key and project name. This is highly recommended for development.

## Running Polkaquery Components

### Step 1: Automated Tool Generation

The first time you run the Polkaquery server, it will automatically detect that the tool definition cache is empty. It will then connect to the necessary sources (Subscan's website, an AssetHub node) and generate the required `.json` tool definitions. These are saved to the `polkaquery_tool_definitions/` directory, which acts as a persistent cache.

On all subsequent startups, the server will find these cached files and load them directly, which is much faster.

To force a regeneration of the tools, simply delete the contents of the `polkaquery_tool_definitions/subscan` and `polkaquery_tool_definitions/assethub` directories before starting the server.

### Step 2: Run the Polkaquery FastAPI Server

The Polkaquery server provides the `/llm-query/` endpoint that AI agents will call.

1.  Ensure your `.env` file is correctly set up.
2.  From the project root (`polkaquery_project_root/`), run:
    ```bash
    uvicorn polkaquery.main:app --reload --port 8000 --env-file .env
    ```
    The server should start and be accessible at `http://127.0.0.1:8000`. Using the `--env-file` flag is the recommended way to ensure all environment variables, including those for LangSmith, are loaded correctly before the application starts.

### Clearing the Query Cache (For Testing)

Polkaquery uses an in-memory cache for API responses and LLM decisions to speed up repeated queries. Because this cache is in-memory, it is automatically cleared every time you restart the FastAPI server.

**To clear the cache, simply stop and restart the `uvicorn` server process.** This is the easiest way to ensure you are getting fresh, non-cached results when testing.

### Step 3: Run Integration Examples

Make sure the Polkaquery FastAPI server (Step 2) is running before executing these client examples.

#### Langchain Client with Google Gemini

This example demonstrates using Polkaquery as a tool within a Langchain agent powered by Google Gemini.

1.  Ensure `GOOGLE_GEMINI_API_KEY` is set in your `.env` file.
2.  Navigate to the project root.
3.  Run the Langchain Gemini example script:
    ```bash
    python integrations/langchain_client/langchain_gemini_example.py
    ```

#### Ollama Client

This example shows a more direct interaction with a locally hosted LLM (via Ollama) to decide when to use Polkaquery.

1.  **Start Ollama Server:** Ensure it's running.
2.  **Pull a Model for Ollama:** Ensure the model specified in `integrations/ollama_client/ollama_polkaquery_example.py` is pulled (e.g., `ollama pull phi3:mini`).
3.  Navigate to the project root.
4.  Run the Ollama client example script:
    ```bash
    python integrations/ollama_client/ollama_polkaquery_example.py
    ```

## Interpreting Outcomes & Examples

This section describes what to expect from the logs and output files generated by the various components.

(Details on interpreting server logs, tool definitions, and client outputs would go here.)

## Agent Integrations

### MCP (Multi-Chain Agent Protocol) Integration

Polkaquery now supports MCP, allowing it to be used as a standard tool by other compliant AI agents in the Polkadot ecosystem.

*   **Tool Specification:** The tool's capabilities are described in the `mcp_tool_spec.json` file in the project root.
*   **Endpoint:** The MCP-compliant endpoint is available at `POST /mcp/v1/query`.

#### Example Usage with Postman

You can test the MCP endpoint using a graphical API client like Postman:

1.  **Method:** `POST`
2.  **URL:** `http://127.0.0.1:8000/mcp/v1/query`
3.  **Headers:** Set `Content-Type` to `application/json`.
4.  **Body:** Select the `raw` JSON option and enter a payload like:
    ```json
    {
      "query": "What is the total issuance of DOT?",
      "network": "polkadot"
    }
    ```

## Future Enhancements (Roadmap Ideas)


* **Agentic Multi-Step Reasoning:** Implement a more advanced agentic loop in `main.py` to allow Polkaquery to make multiple tool calls sequentially to answer complex queries.
* **Expanded Toolset:** Integrate additional data sources and tools, such as:
  * **Governance Data:** Tools to fetch and analyze governance proposals, referenda, and council motions.
  * **DeFi and NFT Data:** Integrate with DeFi protocols and NFT marketplaces on Polkadot parachains.
* **Support for More Data Sources:** Integrate other Polkadot ecosystem APIs (e.g., Polkassembly for governance, specific parachain APIs).
* **Enhanced Caching Mechanism:** Implement a more sophisticated caching strategy (e.g., Redis) to persist cache across server restarts and improve performance.
* **User Interface:** Develop a simple web interface for users to interact with Polkaquery directly.
* **Authentication and Rate Limiting:** Add user authentication and rate limiting to manage API usage effectively.
* **Improved Error Handling:** Enhance error handling and logging for better debugging and user experience.
* **Streaming Data Support:** Implement support for real-time data updates using WebSocket connections to Subscan or other services.


## Contributing

We welcome contributions to Polkaquery! Please open an issue on our GitHub repository to report bugs or suggest enhancements.

## License

This project is licensed under the **GNU General Public License v3.0**. See the [LICENSE](LICENSE) file for details.