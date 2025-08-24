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

from langgraph.graph import StateGraph, END
from .state import GraphState
from . import nodes

def build_graph():
    """Builds and compiles the LangGraph state machine."""
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("route_query", nodes.route_query)
    workflow.add_node("recognize_tool", nodes.recognize_tool)
    workflow.add_node("execute_tool", nodes.execute_tool)
    workflow.add_node("generate_answer", nodes.generate_answer)
    workflow.add_node("handle_error", nodes.handle_error)

    # Define edges
    workflow.set_entry_point("route_query")
    workflow.add_edge("route_query", "recognize_tool")
    workflow.add_edge("recognize_tool", "execute_tool")
    workflow.add_edge("generate_answer", END)
    workflow.add_edge("handle_error", END)

    # Add conditional edges after tool execution
    def decide_next_step(state: GraphState):
        if state.get("error_message"):
            return "handle_error"
        return "generate_answer"

    workflow.add_conditional_edges(
        "execute_tool",
        decide_next_step,
        {
            "handle_error": "handle_error",
            "generate_answer": "generate_answer"
        }
    )

    # Compile the graph into a runnable object
    return workflow.compile()
