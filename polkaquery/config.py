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

from pydantic_settings import BaseSettings
from pydantic import Field
import os

class Settings(BaseSettings):
    """
    Centralized application settings.
    Values are loaded from a .env file or environment variables.
    """
    # API Keys
    google_gemini_api_key: str = Field(..., env="GOOGLE_GEMINI_API_KEY")
    subscan_api_key: str | None = Field(None, env="SUBSCAN_API_KEY")
    tavily_api_key: str | None = Field(None, env="TAVILY_API_KEY")
    onfinality_api_key: str | None = Field(None, env="ONFINALITY_API_KEY")

    # Service URLs
    polkaquery_fastapi_url: str = Field("http://127.0.0.1:8000/llm-query/", env="POLKAQUERY_FASTAPI_URL")
    assethub_ws_url: str = "wss://statemint.api.onfinality.io/public-ws"
    subscan_base_url: str = "https://polkadot.api.subscan.io"

    # Filesystem Paths
    tools_output_directory: str = "polkaquery_tool_definitions"

    # LangSmith Monitoring (Optional)
    langchain_tracing_v2: str = Field("false", env="LANGCHAIN_TRACING_V2")
    langchain_endpoint: str = Field("https://api.smith.langchain.com", env="LANGCHAIN_ENDPOINT")
    langchain_api_key: str | None = Field(None, env="LANGCHAIN_API_KEY")
    langchain_project: str | None = Field(None, env="LANGCHAIN_PROJECT")

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        # Pydantic v2 automatically converts env var names to lowercase,
        # so we don't need case_sensitive = False for this to work.

# Create a single, importable instance of the settings
settings = Settings()
