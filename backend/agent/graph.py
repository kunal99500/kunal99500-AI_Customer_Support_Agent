from dotenv import load_dotenv
load_dotenv(override=True)
import os 
from agent.state import AgentState
from agent.tools import lookup_customer, check_order_status, validate_policy, process_refund, list_orders_for_customer, schedule_pickup
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END






load_dotenv(dotenv_path=r"C:\AI_Customer_Support_Agent\.env")

# ── Step 1: Wrap our plain functions as LangChain "tools" ──────────
# The @tool decorator lets the LLM see the function name, its
# arguments, and the docstring — that's how it knows when to call it.

@tool
def tool_lookup_customer(customer_id: str) -> dict:
    """Look up a customer's profile by their customer ID (e.g. C001)."""
    return lookup_customer(customer_id)


@tool
def tool_check_order_status(order_id: str) -> dict:
    """Check an order's status, item type, and how many days since purchase."""
    return check_order_status(order_id)


@tool
def tool_validate_policy(customer_info: dict, order_info: dict) -> dict:
    """Check refund eligibility against policy rules, given customer info and order info."""
    return validate_policy(customer_info, order_info)


@tool
def tool_process_refund(order_id: str, amount: float) -> dict:
    """Process the refund payment. Only call this AFTER validate_policy returns approved=True."""
    return process_refund(order_id, amount)

@tool
def tool_list_orders_for_customer(customer_id: str) -> dict:
    """List all recent orders for a customer, when they know their customer ID but not their order ID."""
    return list_orders_for_customer(customer_id)


@tool
def tool_schedule_pickup(order_id: str) -> dict:
    """Schedule a return pickup for a physical item after a refund is approved. Call this BEFORE tool_process_refund."""
    return schedule_pickup(order_id)


tools = [tool_lookup_customer, tool_check_order_status, tool_validate_policy, tool_process_refund, tool_list_orders_for_customer]
tools_by_name = {t.name: t for t in tools}

# ── Step 2: Set up the LLM and give it the tools ────────────────────
llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))
llm_with_tools = llm.bind_tools(tools)
SYSTEM_PROMPT = """You are a friendly customer support agent that handles refund requests.
Follow this conversation flow step by step. Do not skip steps or rush ahead.

IMPORTANT: Once you call tool_lookup_customer, you will receive the
customer's real name (e.g. "Sneha Iyer"). From that point onward, address
them by their first name in every reply — e.g. "Sneha, I found your
order..." or "Great news, Sneha!" This makes the conversation feel personal,
not robotic. Use their first name only (not the full name) in normal
conversation.

STEP 1 — Get the customer ID and greet them by name.
If you don't have a customer_id (format: C001, C002, etc.) yet, ask for it warmly.
As SOON as you receive a customer_id (this turn), call tool_lookup_customer
immediately to get their name. Use their first name in this reply and every
reply from now on — e.g. "Thanks Sneha! Let me look into that for you."

STEP 2 — Get the order.
Once you have the customer_id and their name, check if you also have an
order_id (format: O001, O002, etc.).
- If you DO have it, skip to STEP 3.
- If you DON'T have it, call tool_list_orders_for_customer, then list their
  recent orders (item name, order id) and ask which one they mean —
  addressing them by name.

STEP 3 — Confirm the order and ask how you can help.
Once you know the order_id, call tool_check_order_status. Then describe the
order back to them (item name, days since purchase) and ask how you can help
with this order. Do NOT mention refunds or policy yet. Wait for their reply.

STEP 4 — Acknowledge the refund request.
Once the customer says they want a refund, reply with ONLY a short
acknowledgement like "Got it, let me check our refund policy for this
order — one moment please." Make NO tool calls in this reply.

STEP 5 — Run the policy check and decide.
On your next turn, using the customer_id and order_id you ALREADY HAVE,
call the tools in this order:
  a. tool_check_order_status
  b. tool_validate_policy (using the customer info you already have from
     earlier, and this order info)
If approved, a pickup will be scheduled automatically by our system after
your call to tool_process_refund succeeds. Simply call tool_process_refund
once, then tell the customer — by their first name — that their refund is
approved, pickup will be scheduled shortly, and the refund will be credited
once the item is received back.
If denied, do not call tool_process_refund. Clearly explain why — by name —
referencing the reason from validate_policy.

General rules:
- Never ask for a customer_id or order_id you've already received in this conversation.
- Never skip validate_policy.
- If a tool returns "not found", say so clearly and ask them to double check.
- Be warm, conversational, and concise.
"""


# ── Step 3: Define the nodes ────────────────────────────────────────

import time

def agent_node(state: AgentState) -> dict:
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]

    max_retries = 3
    last_error = None
    log_entries = []

    for attempt in range(1, max_retries + 1):
        try:
            response = llm_with_tools.invoke(messages)
            print(f"[DEBUG] Agent response - tool_calls: {response.tool_calls}, content: {response.content[:100]}")

            if response.tool_calls:
                called = [tc["name"] for tc in response.tool_calls]
                log_entries.append(f"Agent decided to call: {called}")
            else:
                log_entries.append("Agent is finalizing its answer...")

            return {
                "messages": [response],
                "reasoning_log": state.get("reasoning_log", []) + log_entries,
            }

        except Exception as e:
            last_error = e
            log_entries.append(f"⚠️ LLM call failed (attempt {attempt}/{max_retries}): {str(e)}")
            if attempt < max_retries:
                time.sleep(1.5 * attempt)  # wait a bit longer each retry

    # All retries exhausted — fail gracefully instead of crashing the app
    log_entries.append(f" LLM call failed after {max_retries} attempts. Giving up.")
    
    fallback = AIMessage(content="I'm having trouble processing your request right now. Please try again in a moment.")

    return {
        "messages": [fallback],
        "reasoning_log": state.get("reasoning_log", []) + log_entries,
    }

def tool_node(state: AgentState) -> dict:
    """Runs whichever tool(s) the LLM just asked for, and logs the result."""
    last_message = state["messages"][-1]
    tool_messages = []
    log_entries = []
    pickup_note = None  # will hold pickup info to inject separately, if any

    for tool_call in last_message.tool_calls:
        tool_fn = tools_by_name[tool_call["name"]]

        try:
            result = tool_fn.invoke(tool_call["args"])

            if isinstance(result, dict) and result.get("found") is False:
                log_entries.append(
                    f"⚠️ {tool_call['name']}({tool_call['args']}) returned NOT FOUND -> {result.get('error')}"
                )
            else:
                log_entries.append(f"✅ Ran {tool_call['name']}({tool_call['args']}) -> {result}")

        except Exception as e:
            result = {"error": f"Tool failed to execute: {str(e)}"}
            log_entries.append(f"❌ {tool_call['name']}({tool_call['args']}) CRASHED -> {str(e)}")

        # Every requested tool call gets EXACTLY one ToolMessage reply —
        # nothing else goes in this list.
        tool_messages.append(
            ToolMessage(content=str(result), tool_call_id=tool_call["id"])
        )

        if tool_call["name"] == "tool_validate_policy" and isinstance(result, dict):
            args = tool_call["args"]
            order_info = args.get("order_info", {})
            order_id = order_info.get("order_id", "unknown")
            amount = order_info.get("amount", "?")
            status_word = "APPROVED" if result.get("approved") else "DENIED"

            audit_line = f"📋 AUDIT — Order {order_id} | ₹{amount} | DECISION: {status_word} | Reason: {result.get('reason')}"
            log_entries.append(audit_line)

            if result.get("approved") and order_id != "unknown":
                pickup_result = schedule_pickup(order_id)
                log_entries.append(f"📦 Auto-scheduled pickup -> {pickup_result}")
                # Save this for later — do NOT append it to tool_messages here.
                pickup_note = f"[System note: pickup automatically scheduled for order {order_id}. Details: {pickup_result}]"

    new_messages = tool_messages
    if pickup_note:
        # Safe to add a SystemMessage now, AFTER all required ToolMessages
        # for this turn already exist in new_messages — but to be fully
        # safe with OpenAI's strict ordering rule, we add it as a separate
        # item appended after, in its own list position following the tool replies.
        new_messages = tool_messages + [SystemMessage(content=pickup_note)]

    return {
        "messages": new_messages,
        "reasoning_log": state.get("reasoning_log", []) + log_entries,
    }

# ── Step 4: Define the routing logic ────────────────────────────────

def should_continue(state: AgentState) -> str:
    """After the agent node runs: does it want to call a tool, or is it done?"""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END


# ── Step 5: Build the graph ─────────────────────────────────────────

graph_builder = StateGraph(AgentState)
graph_builder.add_node("agent", agent_node)
graph_builder.add_node("tools", tool_node)

graph_builder.set_entry_point("agent")
graph_builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
graph_builder.add_edge("tools", "agent")  # after tools run, go back to agent

refund_graph = graph_builder.compile()