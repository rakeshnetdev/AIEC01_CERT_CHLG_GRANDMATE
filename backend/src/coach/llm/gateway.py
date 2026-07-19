import os
from typing import List, Dict, Any
from config.settings import get_settings

# NOTE: litellm is imported lazily inside chat(). Importing it at module scope costs ~4s
# (it eagerly pulls its whole provider tree, including chromadb), and this module is on the
# import path of coach.agent.graph -- so it was dominating `langgraph dev` startup even
# though nothing is called at import time. Keep it inside the function.

def chat(messages: List[Dict[str, str]], model: str | None = None, **kw) -> str:
    """
    Sends a chat completion request to the primary LLM (Gemini) with a fallback to OpenAI.
    Allows passing additional kwargs to LiteLLM's completion function.
    """
    s = get_settings()

    # Populate API keys into environment variables for LiteLLM
    if s.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = s.gemini_api_key
    if s.openai_api_key:
        os.environ["OPENAI_API_KEY"] = s.openai_api_key

    primary_model = model or s.llm_model
    fallbacks = [s.llm_fallback_model] if s.llm_fallback_model else []

    # Disable LiteLLM telephony/telemetry logging to clean up logs
    os.environ["LITELLM_LOGGING"] = "FALSE"

    import time
    import logging

    import litellm
    import litellm.exceptions
    
    logger = logging.getLogger(__name__)

    for attempt in range(4):
        try:
            response = litellm.completion(
                model=primary_model,
                messages=messages,
                fallbacks=fallbacks,
                **kw
            )
            return response.choices[0].message.content
        except Exception as e:
            is_rate_limit = isinstance(e, litellm.exceptions.RateLimitError)

            # A configured fallback is the fastest way out of *any* primary failure,
            # including a rate limit. This branch used to sit below a RateLimitError
            # handler that slept 10s, 20s, then 30s before giving up, so a quota-exhausted
            # primary cost a minute of dead time per call and never reached the fallback
            # that would have answered immediately.
            if fallbacks:
                logger.warning(
                    f"Primary model {primary_model} failed ({type(e).__name__}). "
                    f"Falling back to {fallbacks[0]}."
                )
                try:
                    response = litellm.completion(
                        model=fallbacks[0],
                        messages=messages,
                        **kw
                    )
                    return response.choices[0].message.content
                except Exception as fallback_err:
                    logger.error(f"Fallback model query also failed: {fallback_err}")

            # Only back off when there was nothing to fall back to, or the fallback
            # failed as well -- waiting is the only remaining option.
            if is_rate_limit and attempt < 3:
                sleep_time = (attempt + 1) * 10.0
                logger.warning(
                    f"Rate limited and no working fallback. "
                    f"Retrying in {sleep_time:.1f}s (attempt {attempt + 1}/4)."
                )
                time.sleep(sleep_time)
                continue

            raise e
