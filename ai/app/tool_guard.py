"""Tool-call verification wrapper (addendum A.4).

The model sometimes ignores "you must call a tool". Never trust that a tool
was called just because it was requested: check, retry once with an explicit
instruction, then fall back to "insufficient data" instead of guessing.
"""


def invoke_with_required_tools(model, tools: list, messages: list, min_calls: int = 1, max_attempts: int = 2):
    """Invoke a tool-bound model, requiring at least min_calls tool calls.

    Raises RuntimeError after max_attempts — the caller must then return a
    clear "insufficient data, human should check manually" message rather
    than letting the graph continue with an ungrounded answer.
    """
    bound = model.bind_tools(tools, tool_choice="auto")
    attempt_messages = list(messages)
    for _ in range(max_attempts):
        response = bound.invoke(attempt_messages)
        calls = getattr(response, "tool_calls", None) or []
        if len(calls) >= min_calls:
            return response
        attempt_messages = attempt_messages + [
            ("system", "You must call one of the available tools before answering. Do not answer from memory."),
        ]
    raise RuntimeError("Model did not call a required tool after retries — returning 'insufficient data' instead of guessing.")
