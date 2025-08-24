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

from typing import TypedDict, Annotated, Any
from langgraph.graph.message import add_messages

class GraphState(TypedDict):
    """
    Defines the state that is passed between nodes in the graph.
    """
    query: str
    network: str
    route: str
    tool_name: str
    tool_params: dict
    api_response: Any
    final_answer: str
    error_message: str
