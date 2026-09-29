"""Single shared model factory (addendum A.1).

Every agent must import get_model() from here — never instantiate ChatGroq
directly elsewhere, so the model/version is a one-line change.
"""

from langchain_groq import ChatGroq

from .settings import settings


def get_model(temperature: float = 0) -> ChatGroq:
    """openai/gpt-oss-120b on Groq. temperature=0 keeps findings repeatable."""
    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set — put it in ai/.env (see ai/.env.example). "
            "The deterministic /ai/ask path keeps working without it."
        )
    return ChatGroq(
        model=settings.AI_MODEL,
        temperature=temperature,
        reasoning_format="parsed",  # keeps reasoning out of the content field
        max_retries=2,
        api_key=settings.GROQ_API_KEY,  # passed explicitly — never rely on ambient env
    )
