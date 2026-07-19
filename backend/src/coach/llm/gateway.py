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
        except litellm.exceptions.RateLimitError as e:
            if attempt < 3:
                sleep_time = (attempt + 1) * 10.0
                print(f"RateLimitError encountered. Retrying in {sleep_time:.1f}s... (Attempt {attempt+1}/4)")
                time.sleep(sleep_time)
            else:
                raise e
        except Exception as e:
            # If the primary model fails (due to 404, quota limits, or auth errors), invoke the fallback immediately
            if fallbacks:
                logger.warning(f"Primary model {primary_model} query failed: {e}. Trying fallback model {fallbacks[0]}...")
                try:
                    response = litellm.completion(
                        model=fallbacks[0],
                        messages=messages,
                        **kw
                    )
                    return response.choices[0].message.content
                except Exception as fallback_err:
                    logger.error(f"Fallback model query also failed: {fallback_err}")
            raise e

