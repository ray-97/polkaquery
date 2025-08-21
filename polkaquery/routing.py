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

import google.generativeai as genai
import traceback
from polkaquery.core.async_cache import async_cached, llm_cache

VALID_ROUTES = ["assethub", "subscan", "internet_search"]
DEFAULT_ROUTE = "subscan"

@async_cached(llm_cache)
async def route_query_with_llm(query: str, model: genai.GenerativeModel, prompt_template: str) -> str:
    """
    Uses an LLM to determine the best data source (route) for a user query.

    Args:
        query: The user's natural language query.
        model: The initialized Gemini GenerativeModel.
        prompt_template: The prompt template for the router.

    Returns:
        The name of the chosen route (e.g., 'subscan', 'assethub').
    """
    if not model or not prompt_template:
        print(f"WARN [router]: LLM model or prompt not provided. Falling back to default route: {DEFAULT_ROUTE}")
        return DEFAULT_ROUTE

    prompt = prompt_template.format(query=query)

    try:
        generation_config = genai.types.GenerationConfig(temperature=0.0)
        response = await model.generate_content_async(prompt, generation_config=generation_config)
        
        chosen_route = response.text.strip().lower()
        
        if chosen_route in VALID_ROUTES:
            print(f"INFO [router]: LLM routed query to: {chosen_route}")
            return chosen_route
        else:
            print(f"WARN [router]: LLM returned an invalid route: '{chosen_route}'. Falling back to default: {DEFAULT_ROUTE}")
            return DEFAULT_ROUTE
            
    except Exception as e:
        print(f"ERROR [router]: An error occurred during LLM routing: {e}")
        traceback.print_exc()
        return DEFAULT_ROUTE
