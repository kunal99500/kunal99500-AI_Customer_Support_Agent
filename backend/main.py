from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import re

from agent.graph import refund_graph

app = FastAPI()

# Allow the frontend (running on a different port) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # fine for local dev / submission
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for ongoing chat sessions.
# Key = session_id, Value = list of messages so far.
# (This is simple but resets if the server restarts — fine for this project.)
sessions = {}

# Tracks which sessions are mid-refund-check (waiting to run the real decision)
pending_checks = {}

# Tracks known customer_id / order_id per session, so the LLM never has to
# "remember" these purely from scrolling back through conversation history.
# { session_id: {"customer_id": "C001", "order_id": "O001"} }
session_known_ids = {}

REFUND_KEYWORDS = ["refund", "money back", "return this"]

CUSTOMER_ID_PATTERN = re.compile(r"\bC\d{3}\b", re.IGNORECASE)
ORDER_ID_PATTERN = re.compile(r"\bO\d{3}\b", re.IGNORECASE)


class ChatRequest(BaseModel):
    session_id: str
    message: str


def extract_and_store_ids(session_id: str, text: str):
    """Scans any piece of text (customer message OR agent reply) for
    customer/order ID patterns and remembers them for this session."""
    known = session_known_ids.setdefault(session_id, {})

    customer_match = CUSTOMER_ID_PATTERN.search(text)
    if customer_match:
        known["customer_id"] = customer_match.group().upper()

    order_match = ORDER_ID_PATTERN.search(text)
    if order_match:
        known["order_id"] = order_match.group().upper()

    print(f"[DEBUG] session={session_id[:20]}... known_ids_now={known}")  # ADD THIS

def run_graph_with_known_ids(session_id: str, history: list) -> dict:
    """Runs the LangGraph agent, but first injects a reminder of any IDs
    we already know for this session, so the LLM doesn't need to re-derive
    them from scattered conversation history."""
    known = session_known_ids.get(session_id, {})

    reminder_parts = []
    if known.get("customer_id"):
        reminder_parts.append(f"customer_id={known['customer_id']}")
    if known.get("order_id"):
        reminder_parts.append(f"order_id={known['order_id']}")

    print(f"[DEBUG] session={session_id[:20]}... reminder_parts={reminder_parts}")

    messages_to_send = history
    if reminder_parts:
        reminder = SystemMessage(
            content=f"[Known so far: {', '.join(reminder_parts)}. Do not ask for these again — use them directly.]"
        )
        messages_to_send = history + [reminder]

    try:
        return refund_graph.invoke(
            {"messages": messages_to_send, "reasoning_log": []},
            config={"recursion_limit": 12},
        )
    except Exception as e:
        # Catches recursion errors or any other graph failure, so the
        # customer gets a clean message instead of a 500 server error.
        fallback_msg = AIMessage(
            content="I'm sorry, something went wrong while processing your request. Please try again or contact support directly."
        )
        return {
            "messages": messages_to_send + [fallback_msg],
            "reasoning_log": [f" Graph execution failed: {str(e)}"],
        }

@app.post("/chat")
def chat(request: ChatRequest):
    history = sessions.get(request.session_id, [])

    # ── Checkpoint: if this session was waiting to run the real check,
    # run it now (this is the "continue" message from the frontend's auto-trigger)
    if pending_checks.get(request.session_id):
        pending_checks[request.session_id] = False
        history.append(HumanMessage(content="Please proceed with checking the refund policy now."))

        result = run_graph_with_known_ids(request.session_id, history)
        sessions[request.session_id] = result["messages"]

        return {
            "reply": result["messages"][-1].content,
            "reasoning_log": result["reasoning_log"],
        }

    # ── Normal turn: track any IDs mentioned in the customer's message ──
    extract_and_store_ids(request.session_id, request.message)

    history.append(HumanMessage(content=request.message))

    # If the customer just asked for a refund, force a pause turn instead
    # of letting the LLM jump straight to the decision.
    wants_refund = any(word in request.message.lower() for word in REFUND_KEYWORDS)

    if wants_refund:
        pause_reply = "Got it — let me check our refund policy for this order. One moment please."
        history.append(AIMessage(content=pause_reply))
        sessions[request.session_id] = history
        pending_checks[request.session_id] = True

        return {
            "reply": pause_reply,
            "reasoning_log": ["⏸️ Customer requested a refund — pausing before policy check..."],
        }

    # Otherwise, run the graph as normal (greeting, asking for IDs, listing orders, etc.)
    result = run_graph_with_known_ids(request.session_id, history)
    sessions[request.session_id] = result["messages"]

    # Also capture any IDs the AGENT itself surfaced in its reply
    # (e.g. "I found your order with ID O001" — the agent said it first)
    extract_and_store_ids(request.session_id, result["messages"][-1].content)

    return {
        "reply": result["messages"][-1].content,
        "reasoning_log": result["reasoning_log"],
    }


@app.get("/health")
def health():
    return {"status": "ok"}