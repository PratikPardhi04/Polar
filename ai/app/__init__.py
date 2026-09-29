"""Shared LangChain/LangGraph stack (AI addendum A.1–A.5).

Every agent imports the model factory, tools, structured-output helper and
tool guard from here — never instantiates ChatGroq or parses model freeform
text anywhere else.
"""
