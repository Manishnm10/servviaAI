import datetime
import asyncio

from django_core.config import Config
from rag_service.openai_service import make_openai_request

# Prefer Servvia medical-aware condense prompt; fall back to env prompt if not available
try:
    from django_core.servvia_prompts import CONDENSE_QUERY_PROMPT as SERVVIA_CONDENSE_QUERY_PROMPT
except Exception:
    SERVVIA_CONDENSE_QUERY_PROMPT = None


async def condense_query_prompt(original_query, chat_history):
    """
    Condense the prompt / query with the chat history & input message / query of the client.
    """
    template = SERVVIA_CONDENSE_QUERY_PROMPT or Config.REPHRASE_QUESTION_PROMPT
    condense_prompt = template.format(
        chat_history=chat_history,
        question=original_query,
    )
    return condense_prompt


async def rephrase_query(original_query, chat_history=None):
    """
    Rephrase and return the input query with chat history (if available) from openAI.
    """
    rephrased_response = {}
    rephrased_query = None
    rephrase_start_time = None
    rephrase_end_time = None
    rephrase_completion_tokens = 0
    rephrase_prompt_tokens = 0
    rephrase_total_tokens = 0
    rephrase_exception = None
    rephrase_retries = 0

    rephrased_response.update(
        {
            "original_query": original_query,
            "rephrased_query": rephrased_query,
            "rephrase_start_time": rephrase_start_time,
            "rephrase_end_time": rephrase_end_time,
            "completion_tokens": rephrase_completion_tokens,
            "prompt_tokens": rephrase_prompt_tokens,
            "total_tokens": rephrase_total_tokens,
            "rephrase_exception": rephrase_exception,
            "rephrase_retries": rephrase_retries,
        }
    )

    rephrase_start_time = datetime.datetime.now()

    if chat_history:
        condense_prompt = await condense_query_prompt(original_query, chat_history)
        rephrased_question_response, rephrase_exception, rephrase_retries = await make_openai_request(condense_prompt)
        if rephrased_question_response:
            rephrased_query = rephrased_question_response.choices[0].message.content
            usage = getattr(rephrased_question_response, "usage", None)
            if usage:
                rephrase_completion_tokens = getattr(usage, "completion_tokens", 0)
                rephrase_prompt_tokens = getattr(usage, "prompt_tokens", 0)
                rephrase_total_tokens = getattr(usage, "total_tokens", 0)
        else:
            rephrased_query = original_query
    else:
        rephrased_query = original_query

    rephrase_end_time = datetime.datetime.now()

    rephrased_response.update(
        {
            "original_query": original_query,
            "rephrased_query": rephrased_query,
            "rephrase_start_time": rephrase_start_time,
            "rephrase_end_time": rephrase_end_time,
            "completion_tokens": rephrase_completion_tokens,
            "prompt_tokens": rephrase_prompt_tokens,
            "total_tokens": rephrase_total_tokens,
            "rephrase_exception": rephrase_exception,
            "rephrase_retries": rephrase_retries,
        }
    )

    return rephrased_response
