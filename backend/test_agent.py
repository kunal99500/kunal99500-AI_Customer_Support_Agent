from agent.graph import refund_graph
from langchain_core.messages import HumanMessage

result = refund_graph.invoke({
    "messages": [HumanMessage(content="I want a refund for order O001, my customer id is C001")],
    "reasoning_log": [],
})

print("\n--- FINAL ANSWER ---")
print(result["messages"][-1].content)

print("\n--- REASONING LOG ---")
for line in result["reasoning_log"]:
    print("-", line)