"""Route questions to read-only SQL, local RAG, and the LLM."""

from typing import Any, Dict

from .llm import generate_answer
from .rag import retrieve_context
from .sql_agent import answer_sql_question

SQL_TERMS = (
    "how many",
    "count",
    "number",
    "rate",
    "percentage",
    "percent",
    "average",
    "highest",
    "lowest",
    "total",
    "headcount",
    "department",
    "overtime",
    "high risk",
    "medium risk",
    "low risk",
    "predicted to leave",
    "satisfaction",
)

RAG_TERMS = (
    "what is",
    "what are",
    "what factors",
    "define",
    "definition",
    "meaning",
    "explain",
    "why",
    "associated with",
    "contribute",
    "cause",
    "concept",
    "knowledge",
)


def answer_question(question: str) -> Dict[str, Any]:
    normalized = question.lower().strip()

    # Determine if question might need SQL or RAG
    wants_sql = any(term in normalized for term in SQL_TERMS)
    wants_rag = any(term in normalized for term in RAG_TERMS)

    # Attempt SQL query if requested
    sql_result = answer_sql_question(question) if wants_sql else None

    # Retrieve RAG context if explicitly requested, or if no SQL matched
    needs_rag = wants_rag or (sql_result is None)
    rag_context = retrieve_context(question) if needs_rag else ""

    # Generate final answer via LLM (or fallback logic)
    answer = generate_answer(question, sql_result, rag_context)

    sources = []
    if sql_result and sql_result.get("rows"):
        sources.append("PostgreSQL")
    elif sql_result and not sql_result.get("rows") and sql_result.get("sql"):
        sources.append("PostgreSQL (Query attempted)")
    if rag_context:
        sources.append("knowledge.txt")

    result: Dict[str, Any] = {
        "answer": answer,
        "source": " + ".join(sources) or "General Knowledge",
    }
    if sql_result and sql_result.get("sql"):
        result["sql_used"] = sql_result["sql"]
    if sql_result and sql_result.get("rows") is not None:
        result["data"] = sql_result["rows"]

    return result
