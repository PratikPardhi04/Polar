"""Grounded structured output (addendum A.3).

openai/gpt-oss-120b fails on strict JSON-schema mode, so every agent goes
through this helper with method="function_calling" — never parses raw
freeform text with string matching.
"""

from typing import TypeVar

from langchain_groq import ChatGroq
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def structured_call(model: ChatGroq, schema: type[T], prompt, **kwargs) -> T:
    """Invoke the model and return schema-validated output or raise."""
    structured_model = model.with_structured_output(
        schema,
        method="function_calling",  # NOT the default strict mode
        include_raw=True,
    )
    result = structured_model.invoke(prompt, **kwargs)
    parsed = result.get("parsed") if isinstance(result, dict) else getattr(result, "parsed", None)
    if parsed is None:
        raw = result.get("raw") if isinstance(result, dict) else result
        raise ValueError(f"Model failed to produce valid {schema.__name__}: {raw}")
    return parsed
