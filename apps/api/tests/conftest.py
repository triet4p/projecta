"""Explicit test-only LLM configuration; production has no source defaults."""

import os

for _name, _value in {
    "PROJECTA_LLM_TYPE": "openai-response",
    "PROJECTA_LLM_BASE_URL": "https://api.deepseek.com",
    "PROJECTA_LLM_API_KEY": "test-key",
    "PROJECTA_LLM_MODEL": "deepseek-v4-flash",
}.items():
    os.environ.setdefault(_name, _value)
