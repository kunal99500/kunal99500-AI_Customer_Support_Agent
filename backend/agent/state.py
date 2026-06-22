from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # 'messages' holds the full conversation + tool calls + tool results.
    # add_messages is a special reducer: it APPENDS new messages
    # instead of overwriting the list each time.
    messages: Annotated[list, add_messages]

    # We'll also track a simple log of what the agent did,
    # in plain English, for the admin dashboard.
    reasoning_log: list