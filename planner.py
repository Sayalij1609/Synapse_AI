import logging
import os
import re
from typing import List, Optional, Any

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field, field_validator

# -----------------------------
# Load Environment Variables
# -----------------------------
load_dotenv()

# -----------------------------
# Configure Logging
# -----------------------------
logger = logging.getLogger("synapse.planner")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# -----------------------------
# Structured Output Model
# -----------------------------
class SubtaskItem(BaseModel):
    """An independent research subtask decomposed by the planner."""
    subtask_id: str = Field(
        ...,
        description="Unique ID for the subtask, e.g. 'subtask_1'."
    )
    question: str = Field(
        ...,
        description="Focused sub-question to be investigated."
    )
    search_queries: List[str] = Field(
        default_factory=list,
        description="1 to 2 focused search queries for this sub-question."
    )


class ResearchPlan(BaseModel):
    """Structured plan produced by the Research Planner Agent."""

    main_topic: str = Field(
        ...,
        description="The central topic or subject being researched."
    )
    research_objective: str = Field(
        ...,
        description="A concise, high-level statement summarizing the core research objective."
    )
    sub_questions: List[str] = Field(
        default_factory=list,
        description="5 to 8 targeted sub-questions addressing distinct dimensions of the topic."
    )
    search_queries: List[str] = Field(
        default_factory=list,
        description="5 to 8 focused, non-redundant search queries optimized for live web search."
    )
    subtasks: List[SubtaskItem] = Field(
        default_factory=list,
        description="List of independent research subtasks to be executed concurrently."
    )
    required_source_types: List[str] = Field(
        default_factory=lambda: ["official", "academic", "news", "industry"],
        description="Types of authoritative sources required (e.g. official, academic, news, industry)."
    )
    original_query: Optional[str] = Field(
        default=None,
        description="The original, unmodified user research query."
    )

    def model_post_init(self, __context: Any) -> None:
        """Harmonize subtasks, sub_questions, and search_queries."""
        # 1. If subtasks are provided, populate sub_questions and search_queries
        if self.subtasks and not self.sub_questions:
            self.sub_questions = [s.question for s in self.subtasks]
        if self.subtasks and not self.search_queries:
            all_queries = []
            for s in self.subtasks:
                all_queries.extend(s.search_queries)
            self.search_queries = all_queries

        # 2. If subtasks are missing but sub_questions exist, build subtasks
        if not self.subtasks and self.sub_questions:
            built_subtasks = []
            for idx, sq in enumerate(self.sub_questions, 1):
                # Map query to sub-question or use sub-question itself
                queries_for_sq = []
                if idx - 1 < len(self.search_queries):
                    queries_for_sq.append(self.search_queries[idx - 1])
                else:
                    queries_for_sq.append(f"{self.main_topic} {sq[:40]}")

                built_subtasks.append(SubtaskItem(
                    subtask_id=f"subtask_{idx}",
                    question=sq,
                    search_queries=queries_for_sq
                ))
            self.subtasks = built_subtasks

        # Ensure search_queries is never empty
        if not self.search_queries and self.main_topic:
            self.search_queries = [f"{self.main_topic} overview developments"]

        # Ensure sub_questions is never empty
        if not self.sub_questions and self.main_topic:
            self.sub_questions = [f"What are key developments in {self.main_topic}?"]

    def to_markdown(self) -> str:
        """Format the research plan as human-readable Markdown."""
        lines = [
            f"### 📋 Research Plan: {self.main_topic}",
            "",
            f"**Research Objective:**",
            f"{self.research_objective}",
            "",
            f"**Key Sub-Questions:**",
        ]
        for i, sq in enumerate(self.sub_questions, 1):
            lines.append(f"{i}. {sq}")

        if self.subtasks:
            lines.extend([
                "",
                "**Concurrent Research Subtasks:**",
            ])
            for st in self.subtasks:
                q_text = ", ".join(f"`{q}`" for q in st.search_queries) if st.search_queries else "N/A"
                lines.append(f"- **[{st.subtask_id}]** {st.question} (Queries: {q_text})")

        lines.extend([
            "",
            "**Targeted Search Queries:**",
        ])
        for q in self.search_queries:
            lines.append(f"- `{q}`")

        lines.extend([
            "",
            f"**Required Source Types:**",
            f"{', '.join(self.required_source_types)}",
        ])
        return "\n".join(lines)


# -----------------------------
# Planner LLM Config
# -----------------------------
def get_planner_llm(model: Optional[str] = None) -> ChatGroq:
    """Instantiate a ChatGroq LLM for the planner with configurable parameters."""
    model_name = (
        model
        or os.getenv("PLANNER_MODEL")
        or os.getenv("GROQ_MODEL")
        or "qwen/qwen3.8-27b"
    )
    temperature = float(os.getenv("PLANNER_TEMPERATURE", "0.1"))
    max_tokens = int(os.getenv("PLANNER_MAX_TOKENS", "1500"))

    logger.info("Initializing Planner LLM (model=%s, temp=%.2f, max_tokens=%d)", model_name, temperature, max_tokens)
    return ChatGroq(
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )


# -----------------------------
# Fallback Plan Generator
# -----------------------------
def create_fallback_plan(query: str) -> ResearchPlan:
    """Create a safe, deterministic research plan if LLM output fails validation."""
    clean_query = query.strip()
    logger.warning("Generating deterministic fallback plan for query: '%s'", clean_query)

    return ResearchPlan(
        main_topic=clean_query,
        research_objective=f"Analyze key trends, developments, challenges, and future outlook for '{clean_query}'.",
        sub_questions=[
            f"What is the current status and foundational background of '{clean_query}'?",
            f"What are the major challenges, breakthroughs, and real-world impacts of '{clean_query}'?",
            f"Who are the key players, organizations, and stakeholders involved in '{clean_query}'?",
            f"What are the economic, social, and geopolitical implications of '{clean_query}'?",
            f"What are the future projections and strategic recommendations for '{clean_query}'?",
        ],
        search_queries=[
            f"{clean_query} overview current status",
            f"{clean_query} major challenges breakthroughs",
            f"{clean_query} key players organizations involved",
            f"{clean_query} economic social impact analysis",
            f"{clean_query} future trends market impact",
        ],
        required_source_types=["official", "academic", "news", "industry"],
        original_query=clean_query,
    )


# -----------------------------
# Research Planner Agent
# -----------------------------
class ResearchPlannerAgent:
    """
    Dedicated Research Planner Agent.
    Decomposes user queries into structured ResearchPlan instances.
    """

    def __init__(self, model: Optional[str] = None):
        self.llm = get_planner_llm(model)
        self.prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are an elite Research Planning Agent for an autonomous multi-agent intelligence system.
Your job is to analyze the user's research request and decompose it into a structured, highly focused research plan.

Guidelines:
1. Identify the core topic and formulate an overarching, analytical research objective.
2. Generate 5 to 8 targeted sub-questions covering different dimensions (fundamentals, current state, challenges, breakthroughs, key players, economic/social impact, future outlook, strategic recommendations).
3. Generate 5 to 8 distinct, focused search queries optimized for search engines (DuckDuckGo).
   - Ensure queries are diverse and non-redundant.
   - Avoid generic single-word queries; use targeted phrases and keywords.
   - Cover multiple angles: who, what, when, where, why, how.
4. Specify authoritative source types (e.g., official, academic, news, industry).
5. DO NOT generate the final research report or answer the questions. Only formulate the research plan.
"""
            ),
            (
                "human",
                "Create a structured research plan for the following user request:\n\n{query}"
            )
        ])

    def plan(self, query: str) -> ResearchPlan:
        """
        Generate a validated ResearchPlan for the provided query.
        Handles parsing and LLM errors safely.
        """
        clean_query = query.strip()
        logger.info("Decomposing research query: '%s'", clean_query)

        if not clean_query:
            return create_fallback_plan("General Research Query")

        # 1. Primary path: with_structured_output
        try:
            structured_chain = self.prompt | self.llm.with_structured_output(ResearchPlan)
            plan = structured_chain.invoke({"query": clean_query})

            if isinstance(plan, ResearchPlan):
                plan.original_query = clean_query
                logger.info(
                    "Research plan created successfully with %d sub-questions and %d search queries.",
                    len(plan.sub_questions),
                    len(plan.search_queries)
                )
                return plan

            if isinstance(plan, dict):
                plan["original_query"] = clean_query
                validated_plan = ResearchPlan(**plan)
                logger.info("Research plan validated from dict successfully.")
                return validated_plan

        except Exception as e:
            logger.warning("Structured output call encountered an issue: %s. Attempting fallback parser.", str(e))

        # 2. Secondary path: Prompt LLM for JSON and parse manually
        try:
            json_prompt = ChatPromptTemplate.from_messages([
                (
                    "system",
                    """You are a research planner. Respond with ONLY a valid JSON object matching this schema:
{{
  "main_topic": "string",
  "research_objective": "string",
  "sub_questions": ["string", "string", "string", "string", "string"],
  "search_queries": ["string", "string", "string", "string", "string"],
  "required_source_types": ["official", "academic", "news", "industry"]
}}
Do not include any explanation or markdown formatting outside the JSON."""
                ),
                ("human", "Research Request: {query}")
            ])

            raw_chain = json_prompt | self.llm | StrOutputParser()
            raw_text = raw_chain.invoke({"query": clean_query}).strip()

            # Clean JSON markdown if wrapped in ```json ... ```
            match = re.search(r"\{[\s\S]*\}", raw_text)
            if match:
                import json
                parsed = json.loads(match.group(0))
                parsed["original_query"] = clean_query
                validated_plan = ResearchPlan(**parsed)
                logger.info("Fallback JSON extraction succeeded.")
                return validated_plan

        except Exception as e2:
            logger.error("Fallback JSON parsing failed: %s", str(e2))

        # 3. Final safe fallback: Rule-based plan
        return create_fallback_plan(clean_query)

    def invoke(self, input_dict: dict) -> dict:
        """
        LangChain-compatible invoke signature.
        Expects {"query": str} or {"topic": str} or {"messages": [...]}.
        """
        query = ""
        if "query" in input_dict:
            query = input_dict["query"]
        elif "topic" in input_dict:
            query = input_dict["topic"]
        elif "messages" in input_dict and input_dict["messages"]:
            last_msg = input_dict["messages"][-1]
            query = last_msg[1] if isinstance(last_msg, tuple) else getattr(last_msg, "content", str(last_msg))

        plan = self.plan(query)
        return {
            "plan": plan.model_dump(),
            "plan_markdown": plan.to_markdown(),
            "search_queries": plan.search_queries,
            "original_query": plan.original_query or query,
        }


def build_planner_agent(model: Optional[str] = None) -> ResearchPlannerAgent:
    """Factory function returning a ResearchPlannerAgent instance."""
    return ResearchPlannerAgent(model=model)


def warmup_planner():
    """Pre-warm planner agent LLM client on backend startup."""
    try:
        get_planner_llm()
        logger.info("Planner LLM client and network connection pool pre-warmed.")
    except Exception as e:
        logger.warning("Planner LLM warmup notice: %s", str(e))

