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
    * [Step 1: Generate Subscan API Tool Definitions](#step-1-generate-subscan-api-tool-definitions)
    * [Step 2: Run the Polkaquery FastAPI Server](#step-2-run-the-polkaquery-fastapi-server)
    * [Step 3: Run Integration Examples](#step-3-run-integration-examples)
        * [Langchain Client with Google Gemini](#langchain-client-with-google-gemini)
        * [Ollama Client](#ollama-client)
5.  [Interpreting Outcomes & Examples](#interpreting-outcomes--examples)
    * [Polkaquery FastAPI Server Logs](#polkaquery-fastapi-server-logs)
    * [Tool Definition Files](#tool-definition-files)
    * [Langchain Client Output (`langchain_output.txt`)](#langchain-client-output-langchain_outputtxt)
    * [Ollama Client Output (`ollama_output.txt`)](#ollama-client-output-ollama_outputtxt)
    * [Visual Examples (`images/` directory)](#visual-examples-images-directory)
6.  [Future Enhancements (Roadmap Ideas)](#future-enhancements-roadmap-ideas)
7.  [Contributing](#contributing)
8.  [License](#license)

---

## Project Description

Polkaquery is a specialized search engine designed for the Polkadot ecosystem. It acts as an intelligent interface between AI agents (built with frameworks like Langchain or interacting with LLMs like those served by Ollama) and Polkadot's on-chain data. Instead of traditional web crawling, Polkaquery translates natural language queries into specific API calls to data sources like Subscan, retrieves the information, and provides a synthesized answer.

The primary goal is to enable AI agents to easily access and understand Polkadot blockchain data, functioning similarly to how tools like Tavily Search provide general web search capabilities to agents. This project aims to fulfill the deliverables outlined in the Web3 Foundation Founders Software Grant Agreement, focusing on creating data loaders and function tools for LLM interaction with on-chain data.

This version uses a Large Language Model (LLM), specifically Google Gemini, for advanced intent recognition, tool selection (from Subscan APIs and internet search via Tavily), and final answer synthesis.

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

1.  Create a `.env` file in the project root (`polkaquery_project_root/`) by copying `.env.example` (if provided) or creating a new one.
2.  Add your API keys to the `.env` file. **All listed keys are important for full functionality**:
    ```env
    SUBSCAN_API_KEY=YOUR_SUBSCAN_API_KEY_HERE         # For Subscan API calls; highly recommended for reliable data.
    GOOGLE_GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE  # Required for Polkaquery server's core LLM functions & Langchain Gemini example.
    TAVILY_API_KEY=YOUR_TAVILY_API_KEY_HERE         # Required for the internet search functionality.
    # OLLAMA_BASE_URL=http://localhost:11434        # Optional, if Ollama runs on a different host/port
    # OLLAMA_MODEL=phi3:mini                        # Optional, default model for Ollama client example
    ```
    * `GOOGLE_GEMINI_API_KEY` is essential for the main Polkaquery server and the Langchain Gemini example.
    * `TAVILY_API_KEY` is needed for the internet search tool to function. Without it, internet searches will use a placeholder.
    * `SUBSCAN_API_KEY` is highly recommended for making calls to the Subscan API. While some Subscan endpoints might work without a key, usage may be limited or less reliable.

## Running Polkaquery Components

### Step 1: Generate Subscan API Tool Definitions

This step parses the Subscan API documentation to create structured JSON definitions for each API endpoint. These definitions are used by the LLM to understand what tools are available.

1.  Navigate to the project root (`polkaquery_project_root/`).
2.  Run the parser script:
    ```bash
    python api_spec_parser.py
    ```
    * By default, this script might be configured to process only a specific API or a limited number for testing (check the `if __name__ == "__main__":` block in the script).
    * To process all APIs, you might need to modify the `main()` call in `api_spec_parser.py` to `main()`. This can take some time.
3.  This will create/populate the `polkaquery_tool_definitions/` directory with individual `.json` files for each parsed Subscan API.

### Step 2: Run the Polkaquery FastAPI Server

The Polkaquery server provides the `/llm-query/` endpoint that AI agents will call.

1.  Ensure your `.env` file is correctly set up with `GOOGLE_GEMINI_API_KEY`, `TAVILY_API_KEY`, and `SUBSCAN_API_KEY`.
2.  Ensure the `polkaquery_tool_definitions/` directory has been populated by `api_spec_parser.py`.
3.  From the project root (`polkaquery_project_root/`), run:
    ```bash
    uvicorn polkaquery.main:app --reload --port 8000
    ```
    The server should start and be accessible at `http://127.0.0.1:8000`. You'll see startup logs indicating if API keys and tool definitions were loaded.

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
    * This script will ask a series of predefined questions.
    * The output, including the agent's thoughts and the final answers, will be printed to the console. You can redirect this to a file like `langchain_output.txt`:
        ```bash
        python integrations/langchain_client/langchain_gemini_example.py > integrations/langchain_client/langchain_output.txt 2>&1
        ```

#### Ollama Client

This example shows a more direct interaction with a locally hosted LLM (via Ollama) to decide when to use Polkaquery.

1.  **Start Ollama Server:**
    * If using the desktop app, ensure it's running.
    * Otherwise, in a new terminal, run: `ollama serve` (and keep it running).
2.  **Pull a Model for Ollama:** The script defaults to `phi3:mini` or `llama3`. Ensure the model specified in `integrations/ollama_client/ollama_polkaquery_example.py` (variable `OLLAMA_MODEL`) is pulled:
    ```bash
    ollama pull phi3:mini 
    # or
    # ollama pull llama3
    ```
3.  Navigate to the project root.
4.  Run the Ollama client example script:
    ```bash
    python integrations/ollama_client/ollama_polkaquery_example.py
    ```
    * This script will simulate an LLM deciding to use Polkaquery and then call it.
    * Output will be printed to the console. Redirect to `ollama_output.txt`:
        ```bash
        python integrations/ollama_client/ollama_polkaquery_example.py > integrations/ollama_client/ollama_output.txt 2>&1
        ```

## Interpreting Outcomes & Examples

### Polkaquery FastAPI Server Logs

* When the FastAPI server starts, it will print warnings if API keys (`GOOGLE_GEMINI_API_KEY`, `SUBSCAN_API_KEY`, `TAVILY_API_KEY`) are missing.
* It will also log the number of Subscan tool definitions loaded from the `polkaquery_tool_definitions/` directory.
* When a query is made to `/llm-query/`, the server logs will show:
    * `DEBUG [main._process_llm_query_logic]: Raw query='...' Network='...'`
    * `DEBUG [gemini_recognizer]: LLM selected tool='...', params={...}` (from the first LLM call for tool selection)
    * `DEBUG [main._process_llm_query_logic]: Recognized intent/tool='...', params={...}`
    * If a Subscan tool is called: `Calling Subscan API (Tool Mode): POST <URL> Body: {...}`
    * If internet search is called: `Performing internet search for: '...'`
    * The final JSON response sent back to the client will include the `answer` and debug fields like `debug_intent`, `debug_params`, `debug_formatted_data`.

### Tool Definition Files

* The `polkaquery_tool_definitions/` directory will contain `.json` files, one for each Subscan API endpoint successfully parsed by `api_spec_parser.py`.
* Each JSON file describes a tool: its `name`, `description`, `api_path`, `api_method`, and `parameters` schema. This is what the `gemini_recognizer.py` loads to inform the LLM about available Subscan tools.

### Langchain Client Output (`langchain_output.txt`)

* **Verbose Agent Output:** If `verbose=True` in `AgentExecutor` (or similar in the simplified Langchain example), you'll see the LLM's decision-making process.
    * For the simplified example, this includes the `LLM Decision (Pydantic object): tool_name='...', input='...', reasoning='...'`.
* **Polkaquery Tool Call:** If the LLM decides to use the `polkaquery_search` tool, you'll see a line like `LLM decided to use PolkaqueryTool. Calling tool...`.
* **Final Answer:** The answer provided by the Polkaquery service after it has processed the query (including its own internal LLM calls for synthesis).
* **Error Messages:** If the agent encounters issues, these will be printed.

### Ollama Client Output (`ollama_output.txt`)

* **LLM Decision:** The JSON output from the first Ollama call, showing whether it decided to use Polkaquery and the formulated `polkaquery_question`.
    ```
    LLM Decision: {'use_polkaquery': True, 'polkaquery_question': 'What is the balance of 13Z7KjGnzdAdMre9cqRwTZHR6F2p36gqBsaNmQwwosiPz8JT as of block 26100918?'}
    ```
* **Polkaquery API Call:** Confirmation that the Polkaquery API was called with the specific payload.
* **Polkaquery API Response:** The JSON response from your Polkaquery FastAPI server.
* **Final Answer:** The `answer` field from the Polkaquery API response is presented as the final answer in this simpler workflow. If Polkaquery failed, it might show a fallback message generated by Ollama.

### Visual Examples (`images/` directory)

The `images/` directory contains screenshots illustrating example interactions:
* **Postman Examples:** Showcasing how to query the Polkaquery FastAPI server's `/llm-query/` endpoint directly using Postman, including sample request bodies and responses.
* **Langchain Tool Output:** Screenshots of the console output when running the `langchain_gemini_example.py`, highlighting the Polkaquery tool being called and the final synthesized answer.

These visual aids can help in understanding the expected request/response formats and the flow of information.

## Future Enhancements (Roadmap Ideas)

* **Agentic Multi-Step Reasoning:** Implement a more advanced agentic loop in `main.py` to allow Polkaquery to make multiple tool calls sequentially to answer complex queries.
* **Expanded Toolset:** Parse and integrate all available Subscan API endpoints.
* **Support for More Data Sources:** Integrate other Polkadot ecosystem APIs (e.g., Polkassembly for governance, specific parachain APIs).
* **Advanced Formatting:** Improve `formatter.py` to provide more detailed and context-aware structured summaries for the final LLM synthesis, especially for complex list-based data.
* **Caching:** Implement caching for frequently requested Subscan data to improve performance and reduce API load.
* **User Authentication & Rate Limiting:** For a publicly hosted API.
* **Streaming Responses:** For a more interactive experience with the LLM.
* **More Sophisticated Error Handling:** Allow the agent/LLM to retry failed tool calls or ask for user clarification.

## Contributing

We welcome contributions to Polkaquery! Whether you're looking to fix a bug, add a new feature, improve documentation, or suggest an idea, your help is appreciated. Here's how you can contribute:

**Ways to Contribute:**

* **Reporting Bugs:** If you find a bug, please open an issue on our GitHub repository. Include as much detail as possible: steps to reproduce, expected behavior, actual behavior, your environment (OS, Python version, library versions), and any relevant logs or screenshots.
* **Suggesting Enhancements:** Have an idea for a new feature or an improvement to an existing one? Open an issue to discuss it. We're particularly interested in:
    * Support for new Subscan API endpoints.
    * Integration with other Polkadot ecosystem data sources.
    * Improvements to the `api_spec_parser.py` for more robust tool definition generation.
    * Enhancements to the LLM prompts for better tool selection or answer synthesis.
    * New integration examples (e.g., for different agent frameworks or LLMs).
* **Pull Requests:** If you'd like to contribute code or documentation:
    1.  **Fork the repository.**
    2.  **Create a new branch** for your feature or bug fix (e.g., `feature/new-subscan-tool` or `fix/parser-bug`).
    3.  **Make your changes.** Ensure your code adheres to any existing style guidelines.
    4.  **Add tests** for any new functionality or bug fixes.
    5.  **Ensure all tests pass.**
    6.  **Update documentation** (README, code comments) as necessary.
    7.  **Submit a pull request** to the main branch. Clearly describe the changes you've made and why.

**Getting Help:**

* If you have questions or need help with your contribution, feel free to open an issue with the "question" label.

We look forward to your contributions to make Polkaquery an even more powerful tool for the Polkadot ecosystem!

## License

This project is licensed under the **GNU General Public License v3.0**. See the [LICENSE](LICENSE) file for details.
