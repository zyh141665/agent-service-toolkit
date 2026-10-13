from datetime import datetime

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from agents.tools import current_datetime


def test_current_datetime_tool_returns_timezone_aware_iso_string():
    result = current_datetime.invoke({})

    parsed_datetime = datetime.fromisoformat(result)
    assert parsed_datetime.tzinfo is not None


def test_tool_node_matches_result_to_tool_call_id():
    tool_call_id = "call-current-datetime"
    model_message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "Current_DateTime",
                "args": {},
                "id": tool_call_id,
                "type": "tool_call",
            }
        ],
    )

    graph = StateGraph(MessagesState)
    graph.add_node("tools", ToolNode([current_datetime]))
    graph.set_entry_point("tools")
    graph.add_edge("tools", END)

    result = graph.compile().invoke({"messages": [model_message]})
    tool_message = result["messages"][-1]

    assert isinstance(tool_message, ToolMessage)
    assert tool_message.name == "Current_DateTime"
    assert tool_message.tool_call_id == tool_call_id
