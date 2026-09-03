"""Google Gemini response generation module for Workforce AI Assistant."""

import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Always load .env located in the backend folder, regardless of CWD
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

LOG_FILE = Path(__file__).resolve().parent / "gemini_debug.log"


def _safe_log(message: str) -> None:
    """Print to stdout with immediate flush and append to local debug log file."""
    print(message, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception:
        pass


def generate_answer(
    question: str,
    sql_result: Optional[Dict[str, Any]] = None,
    rag_context: str = "",
) -> str:
    """Generate a natural conversational answer using Google Gemini or fallback."""
    # Ensure latest .env values are loaded on every invocation
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    raw_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    api_key = raw_key.strip().strip('"').strip("'")
    configured_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

    is_placeholder = api_key in ("", "YOUR_GEMINI_API_KEY", "YOUR_API_KEY", "YOUR_GOOGLE_API_KEY")
    key_exists = bool(api_key and not is_placeholder)

    _safe_log(f"[Gemini Diagnostic] API key exists: {key_exists}")
    _safe_log(f"[Gemini Diagnostic] Model name: {configured_model}")

    # If Gemini is not configured, gracefully use the deterministic fallback
    if not key_exists:
        _safe_log("[Gemini Diagnostic] Gemini API call attempted: False (API key is not configured or is placeholder). Using fallback.")
        return _fallback_answer(sql_result, rag_context)

    _safe_log("[Gemini Diagnostic] Gemini API call attempted: True")

    prompt = f"""You are a concise, helpful HR analytics assistant.
User question: {question}
PostgreSQL result (source of truth for workforce numbers): {sql_result or 'None'}
RAG context for HR/project knowledge: {rag_context or 'None'}

Guidelines:
1. Use PostgreSQL results as the absolute source of truth for numerical workforce statistics.
2. Use RAG context for definitions, explanations, and general knowledge.
3. If both are present, blend them into a natural response.
4. Do NOT invent numbers or columns. If the available data cannot answer the question, say so clearly.
5. Provide a clear, professional, HR-friendly answer."""

    # Candidate models to try: user configured model first, then latest active models
    candidate_models = [configured_model]
    for fallback_model in (
        "gemini-flash-latest",
        "gemini-3.6-flash",
        "gemini-2.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ):
        if fallback_model not in candidate_models:
            candidate_models.append(fallback_model)

    client = None
    try:
        client = genai.Client(api_key=api_key)
    except Exception as init_err:
        err_str = str(init_err)
        if api_key and api_key in err_str:
            err_str = err_str.replace(api_key, "[REDACTED_API_KEY]")
        _safe_log(f"[Gemini Diagnostic] Client initialization failed ({type(init_err).__name__}: {err_str})")
        return _fallback_answer(sql_result, rag_context)

    for target_model in candidate_models:
        _safe_log(f"[Gemini Diagnostic] API call started for model: {target_model}")
        try:
            response = client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                ),
            )
            _safe_log(f"[Gemini Diagnostic] API call succeeded for model: {target_model}")
            _safe_log("[Gemini Diagnostic] response received: True")

            answer_text = ""
            if hasattr(response, "text") and response.text:
                answer_text = response.text
            elif hasattr(response, "candidates") and response.candidates:
                cand = response.candidates[0]
                if hasattr(cand, "content") and cand.content and cand.content.parts:
                    answer_text = "".join(
                        part.text for part in cand.content.parts if hasattr(part, "text") and part.text
                    )

            _safe_log(f"[Gemini Diagnostic] response text length: {len(answer_text)}")

            if answer_text.strip():
                return answer_text.strip()
            else:
                _safe_log(f"[Gemini Diagnostic] Empty text returned from {target_model}. Checking alternatives.")

        except Exception as error:
            err_msg = str(error)
            if api_key and api_key in err_msg:
                err_msg = err_msg.replace(api_key, "[REDACTED_API_KEY]")
            _safe_log(f"[Gemini Diagnostic] exception type/message on {target_model}: {type(error).__name__}: {err_msg}")

            # If error is invalid API key (400) or quota exhausted (429/permission), don't keep cycling models
            if "INVALID_ARGUMENT" in err_msg or "API key not valid" in err_msg or "401" in err_msg:
                break

    _safe_log("[Gemini Diagnostic] Fallback returned due to Gemini API failure.")
    return _fallback_answer(sql_result, rag_context)


def _fallback_answer(sql_result: Optional[Dict[str, Any]], rag_context: str) -> str:
    """Deterministic fallback returning direct database and/or RAG results."""
    sql_explanation = sql_result.get("explanation") if sql_result else None

    if sql_explanation and rag_context:
        return f"{sql_explanation}\n\nContext:\n{rag_context}"
    if sql_explanation:
        return sql_explanation
    if rag_context:
        return rag_context
    return "I could not answer that from the available PostgreSQL data or knowledge document."
