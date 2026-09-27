import logging
import os
import re
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from tools import web_search, scrape_url, multi_web_search
from planner import build_planner_agent, ResearchPlannerAgent, ResearchPlan
from resilience import (
    execute_with_retry,
    execute_with_timeout,
    get_llm_circuit_breaker,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
)

logger = logging.getLogger("synapse.agents")

# -----------------------------
# Load Environment Variables & Configuration
# -----------------------------
load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")
GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "750"))
GROQ_WRITER_MAX_TOKENS = int(os.getenv("GROQ_WRITER_MAX_TOKENS", "4096"))
GROQ_CRITIC_MAX_TOKENS = int(os.getenv("GROQ_CRITIC_MAX_TOKENS", "1024"))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30.0"))

# Primary dedicated LLM instances
query_llm = ChatGroq(model=GROQ_MODEL, temperature=0, max_tokens=100, max_retries=2)
reader_llm = ChatGroq(model=GROQ_MODEL, temperature=0, max_tokens=100, max_retries=2)
writer_llm = ChatGroq(model=GROQ_MODEL, temperature=0.1, max_tokens=GROQ_WRITER_MAX_TOKENS, max_retries=2)
critic_llm = ChatGroq(model=GROQ_MODEL, temperature=0, max_tokens=GROQ_CRITIC_MAX_TOKENS, max_retries=2)

# Fallback LLM instances (using secondary model on rate limit / outage)
query_llm_fallback = ChatGroq(model=GROQ_FALLBACK_MODEL, temperature=0, max_tokens=100, max_retries=2)
reader_llm_fallback = ChatGroq(model=GROQ_FALLBACK_MODEL, temperature=0, max_tokens=100, max_retries=2)
writer_llm_fallback = ChatGroq(model=GROQ_FALLBACK_MODEL, temperature=0.1, max_tokens=GROQ_WRITER_MAX_TOKENS, max_retries=2)
critic_llm_fallback = ChatGroq(model=GROQ_FALLBACK_MODEL, temperature=0, max_tokens=GROQ_CRITIC_MAX_TOKENS, max_retries=2)

# Default LLM export for backwards compatibility
llm = writer_llm


def invoke_chain_resilient(
    primary_chain: Any = None,
    fallback_chain: Optional[Any] = None,
    input_dict: Optional[Dict[str, Any]] = None,
    timeout_seconds: float = LLM_TIMEOUT_SECONDS,
    operation_name: str = "LLM Generation",
    chain: Any = None,
    timeout: Optional[float] = None,
    service_name: Optional[str] = None,
    max_attempts: Optional[int] = None,
    **kwargs
) -> str:
    """
    Invokes LangChain runnable with:
    1. Circuit breaker protection.
    2. Per-operation execution timeout.
    3. Automatic fallback to secondary LLM model on rate limit / timeout / server error.
    """
    active_primary = chain if chain is not None else primary_chain
    active_timeout = timeout if timeout is not None else timeout_seconds
    active_op = service_name or operation_name
    active_input = input_dict or {}

    breaker = get_llm_circuit_breaker()

    # 1. Primary chain attempt
    def _run_primary():
        return breaker.execute(
            lambda: execute_with_timeout(
                lambda: execute_with_retry(
                    lambda: active_primary.invoke(active_input),
                    max_retries=2,
                    initial_delay=0.6,
                    backoff_factor=1.5,
                    operation_name=f"{active_op} (Primary: {GROQ_MODEL})",
                ),
                timeout_seconds=active_timeout,
                operation_name=f"{active_op} Timeout",
                timeout_exception_cls=LLMTimeoutError,
            )
        )

    try:
        return _run_primary()
    except Exception as e:
        logger.warning(
            "Primary LLM chain (%s) failed: %s. Attempting fallback model (%s)...",
            GROQ_MODEL, str(e), GROQ_FALLBACK_MODEL
        )

    # 2. Fallback chain attempt
    if fallback_chain is not None and GROQ_FALLBACK_MODEL != GROQ_MODEL:
        try:
            result = execute_with_timeout(
                lambda: execute_with_retry(
                    lambda: fallback_chain.invoke(input_dict),
                    max_retries=2,
                    initial_delay=0.5,
                    operation_name=f"{operation_name} (Fallback: {GROQ_FALLBACK_MODEL})",
                ),
                timeout_seconds=timeout_seconds,
                operation_name=f"{operation_name} Fallback Timeout",
                timeout_exception_cls=LLMTimeoutError,
            )
            logger.info("Successfully recovered %s using fallback model: %s", operation_name, GROQ_FALLBACK_MODEL)
            return result
        except Exception as e2:
            logger.error("Fallback LLM chain (%s) also failed: %s", GROQ_FALLBACK_MODEL, str(e2))
            raise LLMUnavailableError(
                f"Both primary ({GROQ_MODEL}) and fallback ({GROQ_FALLBACK_MODEL}) LLMs failed: {str(e2)}",
                target=GROQ_MODEL,
                original_exception=e2
            )

    raise LLMUnavailableError(f"LLM call '{operation_name}' failed and no fallback available.", target=GROQ_MODEL)


# -----------------------------
# Search Agent (manual tool call with graceful degradation)
# -----------------------------
def build_search_agent():
    """Returns a callable that searches the web using DuckDuckGo."""
    class SearchAgent:
        def invoke(self, input_dict):
            plan = input_dict.get("plan")
            if plan:
                queries = []
                if isinstance(plan, dict):
                    queries = plan.get("search_queries", [])
                elif hasattr(plan, "search_queries"):
                    queries = plan.search_queries

                if queries:
                    results = multi_web_search(queries[:4], max_results_per_query=3)
                    return {
                        "messages": [("assistant", results)],
                        "queries_used": queries[:4]
                    }

            messages = input_dict.get("messages", [])
            user_msg = messages[-1][1] if messages else ""

            # Extract the query with LLM or fallback to regex
            query = ""
            try:
                search_prompt = ChatPromptTemplate.from_messages([
                    ("system", "Extract the core search query from the user's request. Reply with ONLY the search query, nothing else."),
                    ("human", "{request}")
                ])
                primary_chain = search_prompt | query_llm | StrOutputParser()
                fallback_chain = search_prompt | query_llm_fallback | StrOutputParser()
                query = invoke_chain_resilient(primary_chain, fallback_chain, {"request": user_msg}, timeout_seconds=10.0, operation_name="Search Query Extraction").strip()
            except Exception as e:
                logger.warning("LLM query extraction failed: %s. Using regex keyword fallback.", str(e))
                # Fallback to direct text
                clean_msg = re.sub(r'["\']', '', user_msg)
                words = [w for w in clean_msg.split() if len(w) > 3][:5]
                query = " ".join(words) if words else user_msg[:50]

            results = web_search.invoke(query)
            return {
                "messages": [("assistant", results)],
                "queries_used": [query]
            }

    return SearchAgent()


# -----------------------------
# Reader Agent (manual tool call with graceful degradation)
# -----------------------------
def build_reader_agent():
    """Returns a callable that scrapes a URL from search results."""
    class ReaderAgent:
        def invoke(self, input_dict):
            messages = input_dict.get("messages", [])
            user_msg = messages[-1][1] if messages else ""

            url = ""
            try:
                url_prompt = ChatPromptTemplate.from_messages([
                    ("system", "From the search results below, pick the single most relevant and informative URL. Reply with ONLY the URL, nothing else."),
                    ("human", "{text}")
                ])
                primary_chain = url_prompt | reader_llm | StrOutputParser()
                fallback_chain = url_prompt | reader_llm_fallback | StrOutputParser()
                url = invoke_chain_resilient(primary_chain, fallback_chain, {"text": user_msg}, timeout_seconds=10.0, operation_name="Reader URL Extraction").strip()
            except Exception as e:
                logger.warning("LLM URL picking failed: %s. Extracting first URL from text via regex fallback.", str(e))
                urls = re.findall(r"https?://[^\s)\]]+", user_msg)
                url = urls[0] if urls else ""

            if not url or not url.startswith("http"):
                urls = re.findall(r"https?://[^\s)\]]+", user_msg)
                url = urls[0] if urls else ""

            if url:
                content = scrape_url.invoke(url)
                summary = f"Scraped content from {url}:\n\n{content}"
            else:
                summary = "No valid URL could be discovered or extracted from search results."

            return {"messages": [("assistant", summary)]}

    return ReaderAgent()


# -----------------------------
# Writer Chain & Resilient Invoker
# -----------------------------
writer_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an elite research writer producing publication-grade analytical reports.

OBJECTIVE: Synthesize the provided evidence into a comprehensive, deeply analytical research document.

WRITING REQUIREMENTS:
1. The "summary" MUST be a rich 3-5 sentence executive overview establishing context, significance, and scope of the research topic.
2. Each claim "text" MUST be a detailed 3-6 sentence analytical paragraph that:
   - States the core finding clearly
   - Provides quantitative data, dates, or specifics from the evidence
   - Explains WHY this finding matters in the broader research context
   - Connects to other findings or implications where relevant
3. The "conclusion" MUST be a substantive 3-5 sentence strategic synthesis with forward-looking insights and implications.
4. Write in clear, professional analytical prose. Never copy raw evidence text verbatim — always synthesize and explain.
5. If the evidence contains corrupted, unreadable, or binary text, SKIP it entirely and write only from readable evidence.
6. Produce at least 6-10 detailed claims when sufficient evidence is available.

CITATION RULES:
- Cite sources using [Source N] notation matching the Evidence Catalog source numbers.
- Every factual claim must cite at least one source.
- Do NOT invent citations. Only use source_ids or [Source N] numbers from the Evidence Catalog.
- Multiple sources can support a single claim if relevant.

OUTPUT FORMAT — Clean JSON only:
{{
  "summary": "Rich executive introduction (3-5 sentences establishing context and significance)...",
  "claims": [
    {{
      "claim_id": "claim_1",
      "text": "Detailed analytical paragraph (3-6 sentences) explaining the finding, its data, and its significance...",
      "supporting_source_ids": ["source_id_or_number"],
      "evidence_chunk_ids": ["chunk_id"],
      "confidence": 0.95
    }}
  ],
  "conclusion": "Strategic synthesis with implications and forward-looking outlook (3-5 sentences)..."
}}

Output ONLY the JSON block. No commentary outside the JSON.
"""
    ),
    (
        "human",
        """Research Topic:
{topic}

{research}

Generate the grounded findings JSON:"""
    )
])

writer_chain = writer_prompt | writer_llm | StrOutputParser()
writer_chain_fallback = writer_prompt | writer_llm_fallback | StrOutputParser()


# -----------------------------
# Critic Chain & Resilient Invoker
# -----------------------------
critic_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a professional research reviewer.

Evaluate the report carefully.

Focus on:
- Accuracy
- Structure
- Completeness
- Clarity
- Usefulness
"""
    ),
    (
        "human",
        """Review the following research report.

Report:
{report}

Respond exactly in this format:

Score: X/10

Strengths:
- Point 1
- Point 2

Areas to Improve:
- Point 1
- Point 2

Final Verdict:
One concise sentence.
"""
    )
])

critic_chain = critic_prompt | critic_llm | StrOutputParser()
critic_chain_fallback = critic_prompt | critic_llm_fallback | StrOutputParser()