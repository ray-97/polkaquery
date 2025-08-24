import json
import traceback
from typing import TYPE_CHECKING
from polkaquery.core.async_cache import async_cached, api_cache

if TYPE_CHECKING:
    from polkaquery.core.resource_manager import ResourceManager

@async_cached(api_cache)
async def perform_internet_search(rm: "ResourceManager", search_query: str) -> dict:
    """
    Performs an internet search using the Tavily client from the ResourceManager.
    """
    print(f"INFO [helpers.perform_internet_search]: Performing internet search for: '{search_query}'")
    tavily_client = rm.tavily_client
    
    if tavily_client:
        try:
            response_dict = tavily_client.search(query=search_query, search_depth="advanced", max_results=3, include_answer=True)
            return {
                "code": 0,
                "message": "Tavily search successful",
                "data": {
                    "search_provider": "Tavily",
                    "query_used": search_query,
                    "answer_summary": response_dict.get("answer"),
                    "results": response_dict.get("results", [])
                }
            }
        except Exception as e:
            print(f"ERROR [helpers.perform_internet_search]: Tavily search failed: {e}")
            return {"code": -1, "message": f"Internet search with Tavily failed: {str(e)}", "data": None}
    else:
        return {
            "code": 0, 
            "message": "Placeholder Internet Search", 
            "data": {
                "search_provider": "Placeholder",
                "query_used": search_query,
                "results": [{"title": "Placeholder Search Result", "content": "Tavily client is not configured."}]
            }
        }

async def generate_final_llm_answer(rm: "ResourceManager", original_query: str, network_context: str, processed_data: dict, source_type: str) -> str:
    """
    Synthesizes a final natural language answer using the Gemini model from the ResourceManager.
    """
    model = rm.gemini_model
    if not model:
        return "Error: Google Gemini model is not available or configured."

    data_summary_for_prompt = json.dumps(processed_data, indent=2)
    if len(data_summary_for_prompt) > 25000: 
        data_summary_for_prompt = data_summary_for_prompt[:25000] + "\n... (data truncated)"

    prompt = rm.final_answer_prompt.format(
        original_query=original_query,
        network_context=network_context,
        source_type=source_type,
        data_summary_for_prompt=data_summary_for_prompt
    )
    try:
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"ERROR [helpers.generate_final_llm_answer]: Final LLM answer synthesis failed: {e}")
        return f"Could not generate a natural language summary. Raw data: {data_summary_for_prompt}"

async def generate_error_explanation_with_llm(rm: "ResourceManager", original_query: str, tool_name: str, params: dict, error_message: str) -> str:
    """
    Uses the LLM to translate a technical API error into a user-friendly explanation.
    """
    model = rm.gemini_model
    if not model:
        return "An error occurred, and the assistant required to explain it is also unavailable."

    prompt = rm.error_translator_prompt.format(
        original_query=original_query,
        tool_name=tool_name,
        parameters=json.dumps(params),
        error_message=error_message
    )
    try:
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"ERROR [helpers.generate_error_explanation_with_llm]: LLM error explanation failed: {e}")
        return "An error occurred with the data provider. Please check your parameters and try again."

