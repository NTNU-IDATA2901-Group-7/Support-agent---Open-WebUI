"""
Azure OpenAI model for DeepEval judge metrics.

DeepEval's GEval defaults to api.openai.com, which doesn't accept Azure keys.
This module provides a pre-configured AzureOpenAIModel that all LLM-judge
tests can share.
"""

import os

from deepeval.models import AzureOpenAIModel

judge_model = AzureOpenAIModel(
    model="gpt-4.1-mini",
    deployment_name="gpt-4.1-mini",
    api_key=os.environ.get("OPENAI_API_KEY", ""),
    api_version="2024-12-01-preview",
    base_url="https://solwr-ai-poc.cognitiveservices.azure.com/",
    temperature=0,
)
