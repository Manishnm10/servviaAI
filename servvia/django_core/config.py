import os

from dotenv import dotenv_values, load_dotenv

# load_dotenv()
ENV_CONFIG = dotenv_values(encoding="utf-8")
if os.path.isfile(".config.env"):
    ENV_CONFIG.update(dotenv_values(".config.env", encoding="utf-8"))


def handle_boolean(value=False) -> bool:
    if (
        isinstance(value, str)
        and (
            value.lower() == "true"
            or value.lower() == "t"
            or value.lower() == "yes"
            or value.lower() == "y"
        )
    ) or (isinstance(value, bool) and value == True):
        return True

    return False


class Config:
    # DB config
    WITH_DB_CONFIG = handle_boolean(ENV_CONFIG.get("WITH_DB_CONFIG", False))
    DB_NAME = ENV_CONFIG.get("DB_NAME")
    DB_USER = ENV_CONFIG.get("DB_USER")
    DB_PASSWORD = ENV_CONFIG.get("DB_PASSWORD")
    DB_HOST = ENV_CONFIG.get("DB_HOST")
    DB_PORT = ENV_CONFIG.get("DB_PORT")
    MAX_CONNECTIONS = ENV_CONFIG.get("DB_MAX_CONNECTIONS")
    STALE_TIMEOUT = ENV_CONFIG.get("DB_STALE_TIMEOUT")

    # prompts
    REPHRASE_QUESTION_PROMPT = ENV_CONFIG.get("REPHRASE_QUESTION_PROMPT")
    RERANKING_PROMPT_SINGLE_TEMPLATE = ENV_CONFIG.get(
        "RERANKING_PROMPT_SINGLE_TEMPLATE"
    )
    RERANK_SINGLE_JSON_EXAMPLE = ENV_CONFIG.get("RERANK_SINGLE_JSON_EXAMPLE")
    INTENT_CLASSIFICATION_PROMPT_TEMPLATE = ENV_CONFIG.get(
        "INTENT_CLASSIFICATION_PROMPT_TEMPLATE"
    )
    CONVERSATION_PROMPT = ENV_CONFIG.get("CONVERSATION_PROMPT")
    UNCLEAR_QN_PROMPT = ENV_CONFIG.get("UNCLEAR_QN_PROMPT")
    EXIT_PROMPT = ENV_CONFIG.get("EXIT_PROMPT")
    OUT_OF_CONTEXT_PROMPT = ENV_CONFIG.get("OUT_OF_CONTEXT_PROMPT")
    RESPONSE_GEN_PROMPT = ENV_CONFIG.get("RESPONSE_GEN_PROMPT")

    # Azure OpenAI config
    AZURE_OPENAI_API_KEY = ENV_CONFIG.get("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT = ENV_CONFIG.get("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_VERSION = ENV_CONFIG.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    # Backward-compat stubs — keeps tts.py and any legacy code from crashing
    OPEN_AI_KEY = None
    OPENAI_BASE_URL = None
    # Three-model architecture:
    #   MASTER (gpt-4.1)      — Diagnostician: frontier clinical reasoning, temp=0.2
    #   BRAIN  (gpt-4.1-mini) — Critic/Safety: fast verification, temp=0
    #   CHAT   (gpt-4.1-mini) — Proposer/Lab/TTS/OCR: general-purpose, temp=0.3
    MODEL_MASTER = ENV_CONFIG.get("MODEL_MASTER", "gpt-4.1")
    MODEL_BRAIN = ENV_CONFIG.get("MODEL_BRAIN", "gpt-4.1-mini")
    MODEL_CHAT = ENV_CONFIG.get("MODEL_CHAT", "gpt-4.1-mini")

    # Reasoning models that don't support temperature parameter
    # These models use reasoning_effort instead
    REASONING_MODELS = {"o3-mini", "o3", "o4-mini"}

    # Reasoning effort per model (only for REASONING_MODELS)
    REASONING_EFFORT = {
        "o3-mini": "high",
        "o3": "high",
        "o4-mini": "medium",
    }

    # Groq fallback — used when primary OpenAI/GitHub Models hits 429 rate limit
    GROQ_API_KEY = ENV_CONFIG.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    GROQ_FALLBACK_MODELS = {
        "diagnostician": "llama-3.3-70b-versatile",
        "proposer": "llama-3.1-8b-instant",
        "critic": "llama-3.3-70b-versatile",
        "lab_summarizer": "llama-3.3-70b-versatile",
    }

    # Legacy aliases (backwards compat for code that references old names)
    GPT_3_MODEL = MODEL_CHAT      # → gpt-4.1-mini
    GPT_4_MODEL = MODEL_CHAT      # → gpt-4.1-mini
    GPT_5_MINI_MODEL = MODEL_MASTER  # → gpt-4.1

    TEMPERATURE = ENV_CONFIG.get("TEMPERATURE", 0)
    MAX_TOKENS = ENV_CONFIG.get("MAX_TOKENS", 500)
    CHAT_HISTORY_WINDOW = ENV_CONFIG.get("CHAT_HISTORY_WINDOW", 4)

    # Content Retrieval APIs
    CONTENT_DOMAIN_URL = ENV_CONFIG.get("CONTENT_DOMAIN_URL")
    CONTENT_AUTHENTICATE_ENDPOINT = ENV_CONFIG.get("CONTENT_AUTHENTICATE_ENDPOINT")
    CONTENT_RETRIEVAL_ENDPOINT = ENV_CONFIG.get("CONTENT_RETRIEVAL_ENDPOINT")
    FARMSTACK_ORG_ID = ENV_CONFIG.get("FARMSTACK_ORG_ID", "1")
    FARMSTACK_RETRIEVAL_EMAIL = ENV_CONFIG.get("FARMSTACK_RETRIEVAL_EMAIL", "")

    # Language
    LANGUAGE_BCP_CODE_NATIVE = ENV_CONFIG.get("LANGUAGE_BCP_CODE_NATIVE", "en-US")
    LANGUAGE_SHORT_CODE_NATIVE = os.environ.get("LANGUAGE_SHORT_CODE_NATIVE", "en")

    # Translation
    GOOGLE_APPLICATION_CREDENTIALS = ENV_CONFIG.get("GOOGLE_APPLICATION_CREDENTIALS")
