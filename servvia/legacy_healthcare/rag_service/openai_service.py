import os, re
import asyncio
import datetime
import random
import openai
import time
from openai import (
    RateLimitError,
    APITimeoutError,
    InternalServerError,
)

from django_core.config import Config
from openai import AsyncAzureOpenAI
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from legacy_healthcare.common.constants import Constants


async def make_openai_request(
    prompt_message,
    model=Config.GPT_3_MODEL,
    temperature=0,
    initial_delay: float = 1,
    exponential_base: float = 2,
    jitter: bool = True,
    max_retries: int = 10,
):
    """
    Make OpenAI API request with the prompt message and other relevant OpenAI configuration.
    """
    async_client = AsyncAzureOpenAI(
        api_key=Config.AZURE_OPENAI_API_KEY,
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_version=Config.AZURE_OPENAI_API_VERSION,
    )

    exception_string = ""
    retries = 0
    # base_delay = 5
    # max_retries = 5
    delay = initial_delay
    # Reasoning models (o3-mini, o3, o4-mini) don't support temperature
    is_reasoning = model in getattr(Config, "REASONING_MODELS", set())

    while retries < max_retries:
        try:
            # response = await openai.ChatCompletion.acreate(
            attempt_time = datetime.datetime.now()
            create_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt_message}],
            }
            if is_reasoning:
                # Reasoning models use reasoning_effort instead of temperature
                effort = getattr(Config, "REASONING_EFFORT", {}).get(model, "medium")
                create_kwargs["reasoning_effort"] = effort
            else:
                create_kwargs["temperature"] = temperature
            response = await async_client.chat.completions.create(**create_kwargs)
            return response, exception_string, retries
        except (RateLimitError, APITimeoutError, InternalServerError) as e:
            e_time = datetime.datetime.now()
            exception_string += str(e) + f"\t{str((e_time-attempt_time).total_seconds())} seconds\n"

            print(f"Request failed (Retry {retries + 1}/{max_retries}): {e}")

            # delay = base_delay * (2**retries)
            delay *= exponential_base * (1 + jitter * random.random())

            print(f"Retrying in {delay} seconds...")
            await asyncio.sleep(delay)
            # time.sleep(delay)
            retries += 1
        except Exception as e:
            e_time = datetime.datetime.now()
            exception_string += str(e) + f" \t{str((e_time-attempt_time).total_seconds())} seconds\n"
            return None, exception_string, retries

    print(f"Max retries reached ({max_retries}). Request failed.")
    return (
        None,
        exception_string + f"\nMax retries reached ({max_retries}). Request failed.",
        retries,
    )
