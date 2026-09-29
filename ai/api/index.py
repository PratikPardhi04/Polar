"""Vercel serverless entrypoint (optional).

Deploy the `ai/` directory as its own Vercel project if needed. In practice
Render is the better host for this service (see docs/deployment.md): Groq
gpt-oss-120b reasoning calls routinely take tens of seconds, which blows past
serverless timeouts on free tiers, while a long-lived host simply waits.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402,F401  (Vercel serves this ASGI app)
