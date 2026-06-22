# AI_Customer_Support_Agent

An AI-powered customer support agent that processes e-commerce refund requests through natural conversation. Built with **LangGraph + OpenAI** for agent orchestration, **FastAPI** for the backend, **SQLite** for mock data, and a **vanilla HTML/CSS/JS frontend** with built-in browser voice support.

> **Repository:** [github.com/kunal99500/kunal99500-AI_Customer_Support_Agent](https://github.com/kunal99500/kunal99500-AI_Customer_Support_Agent)

---

## What it does

The agent handles refund requests in a multi-turn conversation:

1. Greets the customer and asks for their customer ID
2. Looks up their orders if they don't remember their order ID
3. Confirms the order with item name and purchase date
4. Asks how it can help — only proceeds with refund logic after the customer explicitly requests one
5. Applies refund policy rules deterministically (fraud check, digital exclusion, tier-based window, delivery status)
6. If approved, automatically schedules a return pickup before processing the refund
7. Explains the decision clearly, referencing the customer by first name

Voice input (speech-to-text) and voice output (text-to-speech) are supported via browser-native APIs — no extra API keys required.

---

## Architecture

```
Frontend (HTML/JS in browser)
  - Chat UI with mic button
  - Admin reasoning panel (color-coded live trace)
  - Voice in/out via Web Speech API
        |
        | HTTP POST /chat
        v
FastAPI backend (main.py)
  - Session memory (per session_id)
  - ID extraction layer (regex-based reminder injection)
  - "Please wait" pause checkpoint
  - Recursion-limit circuit breaker
        |
        v
LangGraph agent loop (graph.py)
  - agent_node  -> calls OpenAI GPT-4o with tool definitions
  - tool_node   -> executes tool calls + audit logging
  - Conditional edges: agent <-> tools -> END
        |
        v
Tools (tools.py) - pure Python, deterministic
  - lookup_customer            -> SQLite query
  - check_order_status         -> SQLite query + date math
  - list_orders_for_customer   -> SQLite query (multi-row)
  - validate_policy            -> policy rules in code
  - schedule_pickup            -> mock logistics call
  - process_refund             -> mock payment call
        |
        v
  SQLite (refund_agent.db)
   - customers (15 profiles)
   - orders (15 orders, varied scenarios)
```

---

## Key design decisions

These are the choices I'd want an evaluator to understand:

**1. LLM for judgment, deterministic code for rules.**
The LLM decides *which* tools to call and *how* to talk to the customer. The actual policy validation runs in plain Python (`validate_policy`) — fraud checks, refund window math, digital-item exclusion. This means the policy can't be "talked around" by a clever prompt, and the rules are testable in isolation.

**2. ID memory layer in the backend, not the LLM.**
Customer/order IDs are extracted via regex from every message and injected as a `[Known so far: ...]` reminder on every LLM call. This prevents the LLM from "forgetting" IDs given earlier in the conversation — a real failure mode I hit during development.

**3. Hard checkpoints for multi-step sequencing.**
The "let me check our refund policy — one moment please" pause is enforced **in code** in `main.py`, not by prompting the LLM. Similarly, return pickup is scheduled automatically server-side once policy passes, rather than relying on the LLM to call two tools in the correct order. LLMs are unreliable at strict multi-step sequencing; code isn't.

**4. Graceful degradation, not silent failures.**
- Tool-level errors (not-found, exceptions) flow back into the LLM as `ToolMessage` content so the agent can apologize sensibly.
- LLM API calls have a retry loop with backoff (3 attempts).
- A recursion limit on the agent loop catches runaway tool-calling and returns a clean fallback message instead of a 500.

**5. Browser-native voice.**
Speech-to-text and text-to-speech use `webkitSpeechRecognition` and `SpeechSynthesis` — no ElevenLabs/Whisper API keys, no added latency or cost. Works out of the box in Chrome/Edge.

---

## Refund policy (summary)

| Rule | Detail |
|---|---|
| Window | 30 days standard, 45 days for gold tier customers |
| Item type | Digital goods are non-refundable |
| Fraud | Flagged customer accounts auto-denied |
| Status | Refund only on orders with status `delivered` |

Full policy in `backend/data/policy.md`.

---

## Setup

### Prerequisites
- Python 3.10+
- A valid OpenAI API key with access to `gpt-4o`
- Chrome or Edge browser (for voice features)

### Install

```bash
git clone https://github.com/kunal99500/kunal99500-AI_Customer_Support_Agent.git
cd kunal99500-AI_Customer_Support_Agent

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

### Configure

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-proj-yourkeyhere
```

### Seed the database

```bash
cd backend
python data/seed.py
```

This creates `refund_agent.db` with 15 customer profiles and 15 orders covering every policy edge case.

### Run the server

```bash
cd backend
uvicorn main:app --port 8000
```

> **Note:** Don't use `--reload` while running test conversations — Uvicorn restarts the Python process on file changes, which clears all in-memory session state.

### Open the frontend

Open `frontend/index.html` directly in Chrome (no build step). It connects to `http://127.0.0.1:8000` by default.

---

## Try it

Sample conversation:

```
You:    Hi, my customer id is C004
Agent:  Thanks Sneha! ...
You:    i don't know my order id
Agent:  Here are your recent orders, Sneha: Headphones (O004) ...
You:    headphones
Agent:  You ordered the Headphones, delivered 42 days ago. How can I help?
You:    i want refund
Agent:  Got it - let me check our refund policy. One moment please.
Agent:  Great news, Sneha! Your refund is approved. Pickup scheduled... refund credited once item received back.
```

Test scenarios demonstrating the policy logic:

| Customer | Order | Outcome | Why |
|---|---|---|---|
| C002 | O002 (Python Course) | Denied | Digital item |
| C005 | O005 (T-Shirt) | Denied | Account flagged for fraud |
| C013 | O013 (Notebook Set) | Denied | Beyond 30-day window |
| C014 | O014 (Speaker, 31 days) | Denied | One day past silver window |
| C015 | O015 (Office Chair) | Denied | Order not yet delivered |
| C012 | O012 (Air Purifier, 44 days) | Approved | Within gold's 45-day window |
| C001 | O001 (Running Shoes) | Approved | All conditions met |

The admin panel on the right shows every tool call, the policy decision, and a one-line audit summary in real time.

---

## Project structure

```
AI_Customer_Support_Agent/
├── backend/
│   ├── main.py                  # FastAPI app + session/ID memory layer
│   ├── agent/
│   │   ├── graph.py             # LangGraph StateGraph + tool wrappers
│   │   ├── state.py             # AgentState definition
│   │   └── tools.py             # 6 tools (CRM lookups + policy + pickup)
│   ├── data/
│   │   ├── seed.py              # Database seeding script
│   │   └── policy.md            # Refund policy document
│   └── refund_agent.db          # SQLite database (created by seed.py)
├── frontend/
│   └── index.html               # Self-contained chat UI + admin panel + voice
├── .env                         # OpenAI API key (not committed)
├── requirements.txt
└── README.md
```

---

## Known limitations

These are intentional scope choices, called out for transparency:

- **Session state is in-memory only.** All conversations reset when the server restarts. A production version would use Redis or a database.
- **Voice recognition struggles with alphanumeric IDs.** Speech-to-text often hears "C001" as "see zero zero one" or similar — the customer can clarify by typing if needed.
- **English-only.** No localization.
- **No authentication.** Anyone can ask about any customer ID. A real system would require login.
- **Mock payment integration.** `process_refund` and `schedule_pickup` simulate success; in production they'd call real payment / logistics APIs.

---

## Tech stack

| Layer | Tech |
|---|---|
| Agent orchestration | LangGraph 0.1.x |
| LLM | OpenAI GPT-4o (function calling) |
| Backend | FastAPI + Uvicorn |
| Database | SQLite |
| Frontend | Vanilla HTML / CSS / JS (no build step) |
| Voice | Web Speech API (browser-native) |

---

## Built by

**Kunal** — [github.com/kunal99500](https://github.com/kunal99500)