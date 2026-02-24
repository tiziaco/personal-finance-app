"""
Insights Graph - Personal Finance Intelligence Engine

Generates structured, deterministic financial insights from transaction data
for dashboard visualization and downstream agent consumption.

Architecture:
- 4 parallel analysis nodes (spending, recurring, trends, behavioral/anomalies)
- Aggregation layer (standardizes outputs to Insight schema)
- Optional LLM enrichment (versioned narrative prompts)
- Returns immediately with templated insights, LLM narratives optional

Execution: LangGraph StateGraph with async/parallel node execution
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

import polars as pl
from langgraph.graph import StateGraph, START, END

from app.agents.insights.state import InsightsConfig, InsightsState
from app.agents.insights.nodes import (
    analyze_spending_behavior,
    analyze_recurring_patterns,
    analyze_trends_and_stability,
    analyze_behavioral_and_anomalies,
)
from app.agents.insights.aggregator import aggregate_insights
from app.agents.insights.prompts import load_narrative_prompt
from app.schemas.insights import Insight
from langfuse.langchain import CallbackHandler
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# LLM Enrichment
# ============================================================================

async def format_insights(state: InsightsState) -> Dict[str, Any]:
    """
    Format insights with optional LLM enrichment.

    - Always includes templated summaries (deterministic)
    - Optionally adds LLM narratives (if enabled in config)
    """
    logger.info(f"Formatting {len(state['raw_insights'])} insights...")

    formatted_insights: List[Insight] = []

    for insight in state["raw_insights"]:
        formatted_insight = insight.model_copy()

        # Add LLM narrative if enabled
        if state["config"].enable_llm_enrichment and state["config"].llm_model:
            try:
                template = load_narrative_prompt(state["config"].narrative_prompt_version)
                llm_prompt = template.format(
                    insight_type=insight.type.value,
                    summary=insight.summary,
                    metrics=insight.supporting_metrics,
                )

                narrative = await state["config"].llm_model.ainvoke(llm_prompt)
                formatted_insight.narrative_analysis = narrative.content if hasattr(narrative, 'content') else str(narrative)

                logger.info(f"Generated LLM narrative for {insight.insight_id}")

            except Exception as e:
                logger.warning(f"LLM enrichment failed for {insight.insight_id}: {e}")
                formatted_insight.narrative_analysis = None

        formatted_insights.append(formatted_insight)

    return {
        "formatted_insights": formatted_insights
    }


# ============================================================================
# Graph Construction
# ============================================================================

def _create_insights_config(user_id: str) -> dict:
    """Create a Langfuse-tagged graph invocation config for the insights agent."""
    return {
        "callbacks": [CallbackHandler()],
        "metadata": {
            "langfuse_user_id": user_id,
            "langfuse_session_id": f"insights-{user_id}",
            "langfuse_tags": ["insights_agent", settings.ENVIRONMENT.value],
        },
    }


def build_insights_graph() -> Any:
    """
    Build and compile the insights graph.

    Graph structure:
    START
        ↓
    [4 Parallel nodes]
        ↓ (fan-in)
    aggregate_insights
        ↓
    format_insights
        ↓
    END
    """
    workflow = StateGraph(InsightsState)

    # Add nodes
    workflow.add_node("analyze_spending", analyze_spending_behavior)
    workflow.add_node("analyze_recurring", analyze_recurring_patterns)
    workflow.add_node("analyze_trends", analyze_trends_and_stability)
    workflow.add_node("analyze_behavioral", analyze_behavioral_and_anomalies)
    workflow.add_node("aggregate", aggregate_insights)
    workflow.add_node("format", format_insights)

    # Start → Parallel nodes
    workflow.add_edge(START, "analyze_spending")
    workflow.add_edge(START, "analyze_recurring")
    workflow.add_edge(START, "analyze_trends")
    workflow.add_edge(START, "analyze_behavioral")

    # Parallel nodes → Aggregation (implicit fan-in)
    workflow.add_edge("analyze_spending", "aggregate")
    workflow.add_edge("analyze_recurring", "aggregate")
    workflow.add_edge("analyze_trends", "aggregate")
    workflow.add_edge("analyze_behavioral", "aggregate")

    # Aggregation → Formatting → End
    workflow.add_edge("aggregate", "format")
    workflow.add_edge("format", END)

    return workflow.compile()


# ============================================================================
# Main Invocation
# ============================================================================

async def generate_insights(
    transactions_df: pl.DataFrame,
    user_id: str,
    config: InsightsConfig = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate insights from transaction data.

    Args:
        transactions_df: Polars DataFrame with transaction data
        user_id: User identifier for Langfuse tracking
        config: InsightsConfig for customization (uses defaults if None)
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)

    Returns:
        Dictionary with:
        - formatted_insights: List of Insight objects
        - metadata: Generation metadata (timestamps, node results)
        - errors: List of errors encountered during generation
    """
    if config is None:
        config = InsightsConfig()

    logger.info("Starting insights generation...")
    start_time = datetime.now()

    # Build graph
    graph = build_insights_graph()

    # Prepare initial state
    initial_state: InsightsState = {
        "transactions_df": transactions_df,
        "config": config,
        "start_date": start_date,
        "end_date": end_date,
        "spending_insights": None,
        "recurring_insights": None,
        "trends_insights": None,
        "behavioral_anomaly_insights": None,
        "raw_insights": [],
        "formatted_insights": [],
        "metadata": {},
        "errors": [],
    }

    # Execute graph
    try:
        final_state = await graph.ainvoke(initial_state, config=_create_insights_config(user_id))

        execution_time = (datetime.now() - start_time).total_seconds()

        logger.info(f"Insights generation complete ({execution_time:.2f}s)")

        return {
            "formatted_insights": final_state["formatted_insights"],
            "metadata": {
                "execution_time_seconds": execution_time,
                "total_insights": len(final_state["formatted_insights"]),
                "llm_enrichment_enabled": config.enable_llm_enrichment,
                "timestamp": datetime.now().isoformat()
            },
            "errors": final_state.get("errors", [])
        }

    except Exception as e:
        logger.error(f"Critical error in insights generation: {e}")
        return {
            "formatted_insights": [],
            "metadata": {
                "execution_time_seconds": (datetime.now() - start_time).total_seconds(),
                "total_insights": 0,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            "errors": [f"Graph execution failed: {str(e)}"]
        }


# ============================================================================
# Sync wrapper for compatibility
# ============================================================================

def generate_insights_sync(
    transactions_df: pl.DataFrame,
    user_id: str,
    config: InsightsConfig = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synchronous wrapper for insights generation.

    Use this if you're in a sync context (e.g., Django view, synchronous API).
    """
    return asyncio.run(
        generate_insights(transactions_df, user_id, config, start_date, end_date)
    )
