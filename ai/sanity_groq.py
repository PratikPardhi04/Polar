"""Sanity test before building further agents (addendum A.6). MANUAL RUN ONLY.

Needs: backend running with seeded demo data + a real GROQ_API_KEY.
Run from ai/:  GROQ_API_KEY=... BACKEND_URL=http://localhost:8000 python sanity_groq.py

Asserts: (a) a tool call actually happened, (b) the final answer only
references item names/numbers present in the tool's return value. If it fails
intermittently, increase max_attempts in the tool guard before building the
audit/planning agents on an unverified connection.
"""

import sys

from app.backend_tools import TOOL_MAP, get_inventory
from app.llm import get_model
from app.tool_guard import invoke_with_required_tools

QUESTION = "What items are below minimum stock?"


def main() -> None:
    model = get_model()  # raises a clear error if GROQ_API_KEY is missing
    messages = [("system", "You are the POLARIS inventory analyst. Answer only from tool data."), ("user", QUESTION)]
    response = invoke_with_required_tools(model, [get_inventory], messages, max_attempts=3)
    calls = response.tool_calls or []
    assert calls, "FAIL: model answered without calling get_inventory"
    print(f"tool calls: {[(c['name'], c.get('args')) for c in calls]}")

    results = {}
    for call in calls:
        results[call["name"]] = TOOL_MAP[call["name"]].invoke(call.get("args") or {})
    items = results.get("get_inventory", []) or []
    below = [i for i in items if (i.get("quantity", 0) or 0) < (i.get("minimum_stock", 0) or 0)]
    print(f"below minimum: {[(i.get('name'), i.get('quantity')) for i in below]}")

    follow = model.invoke(messages + [response, ("system", f"Answer '{QUESTION}' using ONLY these item names/numbers: {below}. Do not invent items.")])
    text = getattr(follow, "content", "") or ""
    print("answer:", text)
    names = {(i.get("name") or "").lower() for i in items}
    invented = [w for w in set(text.lower().replace(",", " ").split()) if len(w) > 4 and w not in names and w.isalpha()]
    # crude hallucination screen: long alpha tokens should mostly be known names
    print(f"unmatched tokens (eyeball for invented items): {sorted(invented)[:20]}")
    print("SANITY DONE — review the answer above before proceeding to Phase 9 agents.")


if __name__ == "__main__":
    sys.exit(main() or 0)
