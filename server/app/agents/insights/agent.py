"""
Insights Graph - Personal Finance Intelligence Engine

Generates structured, deterministic financial insights from transaction data
for dashboard visualization and downstream agent consumption.

Architecture:
- 4 parallel analysis nodes (spending, recurring, trends, behavioral/anomalies)
- Aggregation layer (standardizes outputs to Insight schema)
- Optional LLM enrichment (template summaries + narrative analysis)
- Returns immediately with templated insights, LLM narratives optional

Execution: LangGraph StateGraph with async/parallel node execution
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, TypedDict
from enum import Enum

import polars as pl
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from langchain_core.language_models import BaseLanguageModel

# Import raw async analytical tools
from app.tools.financial import (
    get_spending_summary,
    get_category_insights,
    get_recurring_insights,
    get_trend_insights,
    get_behavioral_patterns,
    get_anomaly_insights,
    get_merchant_insights,
    get_spending_stability_profile,
)
from langfuse.langchain import CallbackHandler
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Enums & Models
# ============================================================================

class InsightType(str, Enum):
    """Insight type categories aligned with PRD."""
    SPENDING_BEHAVIOR = "spending_behavior"
    RECURRING_SUBSCRIPTIONS = "recurring_subscriptions"
    TREND = "trend"
    BEHAVIORAL = "behavioral"
    MERCHANT = "merchant"
    STABILITY = "stability"
    ANOMALY = "anomaly"


class SeverityLevel(str, Enum):
    """Severity levels for insights."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Insight(BaseModel):
    """Standardized insight schema for dashboard."""
    insight_id: str = Field(description="Unique identifier for this insight")
    type: InsightType = Field(description="Category of insight")
    severity: SeverityLevel = Field(description="Severity/urgency level")
    time_window: str = Field(description="Time period analyzed (e.g., 'last_3_months')")
    summary: str = Field(description="Templated summary for dashboard")
    narrative_analysis: Optional[str] = Field(default=None, description="LLM-powered narrative (optional)")
    supporting_metrics: Dict[str, Any] = Field(description="Data supporting the insight")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    section: str = Field(description="Dashboard section: 'spending', 'subscriptions', 'trends', 'behavior', 'anomalies'")


class InsightsConfig(BaseModel):
    """Configuration for insights generation."""
    enable_llm_enrichment: bool = Field(default=False, description="Enable LLM narrative generation")
    llm_model: Optional[Any] = Field(default=None, description="LLM instance for narratives")
    time_window_days: int = Field(default=90, description="Default analysis window in days")
    min_confidence_score: float = Field(default=0.7, description="Min confidence for inclusion")
    include_anomalies: bool = Field(default=True, description="Include anomaly detection")
    anomaly_std_threshold: float = Field(default=2.5, description="Std deviations for anomalies")


class InsightsState(TypedDict):
    """State schema for insights graph."""
    # Input
    transactions_df: pl.DataFrame
    config: InsightsConfig
    start_date: Optional[str]
    end_date: Optional[str]
    
    # Processing (parallel nodes)
    spending_insights: Optional[Dict[str, Any]]
    recurring_insights: Optional[Dict[str, Any]]
    trends_insights: Optional[Dict[str, Any]]
    behavioral_anomaly_insights: Optional[Dict[str, Any]]
    
    # Aggregation
    raw_insights: List[Insight]
    
    # Output
    formatted_insights: List[Insight]
    metadata: Dict[str, Any]
    errors: List[str]


# ============================================================================
# Insight Templates (Deterministic Summaries)
# ============================================================================

INSIGHT_TEMPLATES = {
    InsightType.SPENDING_BEHAVIOR: {
        "top_category": "Your top spending category is {category} at {percentage}% of total expenses ({amount_formatted}). Other major categories are {other_categories}.",
        "category_mismatch": "You have high-frequency but low-impact spending in {category} ({frequency} times, only {total}%), which adds up to {total_amount_formatted}.",
    },
    InsightType.RECURRING_SUBSCRIPTIONS: {
        "subscription_load": "Recurring expenses account for {percentage}% of your total spending, costing {monthly_cost_formatted} per month.",
        "hidden_subscriptions": "Detected {count} potential hidden subscriptions (low-amount, high-frequency): {examples}.",
        "subscription_creep": "Your recurring spending increased by {percentage}% compared to last month ({previous_formatted} → {current_formatted}).",
    },
    InsightType.TREND: {
        "burn_rate_acceleration": "Your monthly spending increased by {growth_rate}% compared to your {comparison_period} average ({previous_avg_formatted} → {current_formatted}).",
        "category_momentum": "Your fastest growing category is {category} ({growth_rate}% increase). Slowest is {slowest_category} ({decline_rate}% decrease).",
    },
    InsightType.BEHAVIORAL: {
        "weekend_bias": "You spend {percentage}% more on weekends ({weekend_formatted}/day) vs weekdays ({weekday_formatted}/day).",
        "seasonal_pattern": "Your spending shows {seasonality_strength}% seasonal variation. Strongest in {peak_month}, lowest in {trough_month}.",
    },
    InsightType.MERCHANT: {
        "concentration_risk": "Top 5 merchants account for {top_5_pct}% of spending. Concentration risk is {risk_level}.",
        "merchant_frequency": "You shop at {merchant_count} unique merchants. Top merchant {merchant} represents {percentage}% of spending.",
    },
    InsightType.STABILITY: {
        "predictability": "Your spending is {profile} (stable: {stable_pct}%, volatile: {volatile_pct}%). Recurring costs form a {baseline_pct}% predictable baseline.",
        "subscription_creep": "Recurring expenses are {status} - {change_percentage}% change from previous month.",
    },
    InsightType.ANOMALY: {
        "outlier_detected": "Detected {count} unusual transactions. Largest anomaly: {merchant} ({amount_formatted}, {std_dev}x normal).",
        "category_spike": "Spending spike in {category}: {spike_percentage}% above normal ({recent_formatted} vs avg {avg_formatted}).",
    },
}


# ============================================================================
# Async Analysis Nodes
# ============================================================================

async def analyze_spending_behavior(state: InsightsState) -> Dict[str, Any]:
    """
    Analyze spending overview and category patterns.
    
    Calls:
    - get_spending_summary()
    - get_category_insights()
    """
    try:
        logger.info("Starting spending behavior analysis...")
        
        spending_summary = await get_spending_summary(
            state["transactions_df"],
            start_date=state["start_date"],
            end_date=state["end_date"]
        )
        
        if not spending_summary.get("success"):
            logger.error(f"get_spending_summary failed: {spending_summary.get('error', 'No error message')}")
        
        category_insights = await get_category_insights(
            state["transactions_df"],
            start_date=state["start_date"],
            end_date=state["end_date"]
        )
        
        if not category_insights.get("success"):
            logger.error(f"get_category_insights failed: {category_insights.get('error', 'No error message')}")
        
        return {
            "spending_insights": {
                "spending_summary": spending_summary,
                "category_insights": category_insights,
                "success": spending_summary.get("success") and category_insights.get("success")
            }
        }
    
    except Exception as e:
        logger.error(f"Error in spending behavior analysis: {e}", exc_info=True)
        logger.debug(f"Spending analysis state: df shape = {state['transactions_df'].shape}")
        return {
            "spending_insights": {
                "spending_summary": None,
                "category_insights": None,
                "success": False,
                "error": str(e)
            }
        }


async def analyze_recurring_patterns(state: InsightsState) -> Dict[str, Any]:
    """
    Analyze recurring expenses and subscriptions.
    
    Calls:
    - get_recurring_insights()
    """
    try:
        logger.info("Starting recurring patterns analysis...")
        
        recurring_insights = await get_recurring_insights(
            state["transactions_df"],
            start_date=state["start_date"],
            end_date=state["end_date"]
        )
        
        if not recurring_insights.get("success"):
            logger.error(f"get_recurring_insights failed: {recurring_insights.get('error', 'No error message')}")
        
        return {
            "recurring_insights": {
                "recurring_insights": recurring_insights,
                "success": recurring_insights.get("success")
            }
        }
    
    except Exception as e:
        logger.error(f"Error in recurring patterns analysis: {e}", exc_info=True)
        logger.debug(f"Recurring analysis state: df shape = {state['transactions_df'].shape}")
        return {
            "recurring_insights": {
                "recurring_insights": None,
                "success": False,
                "error": str(e)
            }
        }


async def analyze_trends_and_stability(state: InsightsState) -> Dict[str, Any]:
    """
    Analyze spending trends and stability profile.
    
    Calls:
    - get_trend_insights()
    - get_spending_stability_profile()
    """
    try:
        logger.info("Starting trends and stability analysis...")
        
        trend_insights = await get_trend_insights(
            state["transactions_df"],
            start_date=state["start_date"],
            end_date=state["end_date"]
        )
        
        if not trend_insights.get("success"):
            logger.error(f"get_trend_insights failed: {trend_insights.get('error', 'No error message')}")
        
        stability_profile = await get_spending_stability_profile(
            state["transactions_df"],
            start_date=state["start_date"],
            end_date=state["end_date"]
        )
        
        if not stability_profile.get("success"):
            logger.error(f"get_spending_stability_profile failed: {stability_profile.get('error', 'No error message')}")
        
        return {
            "trends_insights": {
                "trend_insights": trend_insights,
                "stability_profile": stability_profile,
                "success": trend_insights.get("success") and stability_profile.get("success")
            }
        }
    
    except Exception as e:
        logger.error(f"Error in trends and stability analysis: {e}", exc_info=True)
        logger.debug(f"Trends analysis state: df shape = {state['transactions_df'].shape}")
        return {
            "trends_insights": {
                "trend_insights": None,
                "stability_profile": None,
                "success": False,
                "error": str(e)
            }
        }


async def analyze_behavioral_and_anomalies(state: InsightsState) -> Dict[str, Any]:
    """
    Analyze behavioral patterns, merchant concentration, and anomalies.
    
    Calls:
    - get_behavioral_patterns()
    - get_merchant_insights()
    - get_anomaly_insights() (if enabled)
    """
    try:
        logger.info("Starting behavioral and anomaly analysis...")
        
        behavioral_patterns = await get_behavioral_patterns(
            state["transactions_df"],
            start_date=state["start_date"],
            end_date=state["end_date"]
        )
        
        if not behavioral_patterns.get("success"):
            logger.error(f"get_behavioral_patterns failed: {behavioral_patterns.get('error', 'No error message')}")
        
        merchant_insights = await get_merchant_insights(
            state["transactions_df"],
            start_date=state["start_date"],
            end_date=state["end_date"]
        )
        
        if not merchant_insights.get("success"):
            logger.error(f"get_merchant_insights failed: {merchant_insights.get('error', 'No error message')}")
        
        anomaly_insights = None
        if state["config"].include_anomalies:
            anomaly_insights = await get_anomaly_insights(
                state["transactions_df"],
                start_date=state["start_date"],
                end_date=state["end_date"],
                std_threshold=state["config"].anomaly_std_threshold
            )
            
            if anomaly_insights and not anomaly_insights.get("success"):
                logger.error(f"get_anomaly_insights failed: {anomaly_insights.get('error', 'No error message')}")
        
        return {
            "behavioral_anomaly_insights": {
                "behavioral_insights": behavioral_patterns,
                "merchant_insights": merchant_insights,
                "anomaly_insights": anomaly_insights,
                "success": behavioral_patterns.get("success") and merchant_insights.get("success")
            }
        }
    
    except Exception as e:
        logger.error(f"Error in behavioral and anomaly analysis: {e}", exc_info=True)
        logger.debug(f"Behavioral analysis state: df shape = {state['transactions_df'].shape}")
        return {
            "behavioral_anomaly_insights": {
                "behavioral_insights": None,
                "merchant_insights": None,
                "anomaly_insights": None,
                "success": False,
                "error": str(e)
            }
        }


# ============================================================================
# Aggregation & Formatting
# ============================================================================

def aggregate_insights(state: InsightsState) -> Dict[str, Any]:
    """
    Aggregate results from all parallel analysis nodes.
    
    Transforms tool outputs into standardized Insight objects.
    """
    logger.info("Aggregating insights from all analysis nodes...")
    logger.debug(f"State keys available: {list(state.keys())}")
    
    insights: List[Insight] = []
    errors: List[str] = []
    
    # ===== Spending Behavior Insights =====
    spending_data = state.get("spending_insights", {})
    logger.debug(f"Spending data available: {spending_data is not None}, success: {spending_data.get('success')}")
    if spending_data.get("success"):
        logger.debug(f"Processing spending insights. Keys: {list(spending_data.keys())}")
        try:
            spending_summary = spending_data["spending_summary"]["data"]
            category_insights = spending_data["category_insights"]["data"]
            logger.debug(f"Extracted spending_summary and category_insights successfully")
            
            # Top category insight
            if category_insights and "top_categories" in category_insights:
                top_cats = category_insights["top_categories"]
                if top_cats:
                    top_cat = top_cats[0]
                    template = INSIGHT_TEMPLATES[InsightType.SPENDING_BEHAVIOR]["top_category"]
                    
                    other_cats = ", ".join([f"{c['category']} ({c['percentage']:.1f}%)" 
                                           for c in top_cats[1:4]])
                    
                    summary = template.format(
                        category=top_cat["category"],
                        percentage=f"{top_cat['percentage']:.1f}",
                        amount_formatted=f"${abs(top_cat['total_amount']):.2f}",
                        other_categories=other_cats
                    )
                    
                    insight = Insight(
                        insight_id="top_spending_category",
                        type=InsightType.SPENDING_BEHAVIOR,
                        severity=SeverityLevel.INFO,
                        time_window="last_period",
                        summary=summary,
                        supporting_metrics={
                            "category": top_cat["category"],
                            "percentage": top_cat["percentage"],
                            "amount": top_cat["total_amount"]
                        },
                        confidence=0.95,
                        section="spending"
                    )
                    insights.append(insight)
                    logger.debug(f"✅ Created insight: top_spending_category")
        except Exception as e:
            logger.error(f"Error extracting spending behavior insights: {e}", exc_info=True)
            errors.append(f"Spending behavior extraction: {str(e)}")
    else:
        logger.warning("Spending behavior analysis failed or returned no success flag")
        errors.append("Spending behavior analysis failed")
    
    # ===== Recurring Subscriptions Insights =====
    recurring_data = state.get("recurring_insights", {})
    logger.debug(f"Recurring data available: {recurring_data is not None}, success: {recurring_data.get('success')}")
    if recurring_data.get("success"):
        logger.debug(f"Processing recurring insights. Keys: {list(recurring_data.keys())}")
        try:
            recurring_summary = recurring_data["recurring_insights"]["data"]
            logger.debug(f"Extracted recurring_summary successfully")
            
            if recurring_summary:
                recurring_pct = recurring_summary["insights"].get("total_recurring_percentage", 0)
                
                # Extract monthly recurring cost (estimate)
                monthly_costs = recurring_summary.get("monthly_recurring_costs", [])
                total_monthly = sum([m.get("estimated_monthly_cost", 0) for m in monthly_costs])
                
                template = INSIGHT_TEMPLATES[InsightType.RECURRING_SUBSCRIPTIONS]["subscription_load"]
                summary = template.format(
                    percentage=f"{recurring_pct:.1f}",
                    monthly_cost_formatted=f"${total_monthly:.2f}"
                )
                
                insight = Insight(
                    insight_id="subscription_load_index",
                    type=InsightType.RECURRING_SUBSCRIPTIONS,
                    severity=SeverityLevel.MEDIUM if recurring_pct > 30 else SeverityLevel.INFO,
                    time_window="monthly",
                    summary=summary,
                    supporting_metrics={
                        "percentage": recurring_pct,
                        "monthly_cost": total_monthly,
                        "recurring_count": len(monthly_costs)
                    },
                    confidence=0.85,
                    section="subscriptions"
                )
                insights.append(insight)
                logger.debug(f"✅ Created insight: subscription_load_index")
        except Exception as e:
            logger.error(f"Error extracting recurring insights: {e}", exc_info=True)
            errors.append(f"Recurring insights extraction: {str(e)}")
    else:
        logger.warning("Recurring analysis failed or returned no success flag")
        errors.append("Recurring analysis failed")
    
    # ===== Trend Insights =====
    trends_data = state.get("trends_insights", {})
    logger.debug(f"Trends data available: {trends_data is not None}, success: {trends_data.get('success')}")
    if trends_data.get("success"):
        logger.debug(f"Processing trend insights. Keys: {list(trends_data.keys())}")
        try:
            trend_summary = trends_data["trend_insights"]["data"]
            logger.debug(f"Extracted trend_summary successfully")
            
            if trend_summary:
                # Burn rate acceleration
                latest_mom = trend_summary["insights"].get("latest_mom_growth")
                
                if latest_mom is not None:
                    template = INSIGHT_TEMPLATES[InsightType.TREND]["burn_rate_acceleration"]
                    summary = template.format(
                        growth_rate=f"{latest_mom*100:.1f}",
                        comparison_period="12-month",
                        previous_avg_formatted="$X",
                        current_formatted="$Y"
                    )
                    
                    severity = SeverityLevel.HIGH if latest_mom > 0.15 else \
                              SeverityLevel.MEDIUM if latest_mom > 0.05 else SeverityLevel.INFO
                    
                    insight = Insight(
                        insight_id="burn_rate_acceleration",
                        type=InsightType.TREND,
                        severity=severity,
                        time_window="last_3_months",
                        summary=summary,
                        supporting_metrics={"mom_growth": latest_mom},
                        confidence=0.88,
                        section="trends"
                    )
                    insights.append(insight)
                    logger.debug(f"✅ Created insight: burn_rate_acceleration")
        except Exception as e:
            logger.error(f"Error extracting trend insights: {e}", exc_info=True)
            errors.append(f"Trend insights extraction: {str(e)}")
    else:
        logger.warning("Trend analysis failed or returned no success flag")
        errors.append("Trend analysis failed")
    
    # ===== Behavioral Insights =====
    behavioral_data = state.get("behavioral_anomaly_insights", {})
    logger.debug(f"Behavioral data available: {behavioral_data is not None}, success: {behavioral_data.get('success')}")
    if behavioral_data.get("success"):
        logger.debug(f"Processing behavioral insights. Keys: {list(behavioral_data.keys())}")
        try:
            behavioral_summary = behavioral_data["behavioral_insights"]["data"]
            logger.debug(f"Extracted behavioral_summary successfully")
            
            if behavioral_summary:
                weekend_bias = behavioral_summary["day_of_week"].get("weekend_bias_percentage")
                
                if weekend_bias is not None:
                    template = INSIGHT_TEMPLATES[InsightType.BEHAVIORAL]["weekend_bias"]
                    summary = template.format(
                        percentage=f"{abs(weekend_bias):.1f}",
                        weekend_formatted="$X",
                        weekday_formatted="$Y"
                    )
                    
                    insight = Insight(
                        insight_id="weekend_spending_bias",
                        type=InsightType.BEHAVIORAL,
                        severity=SeverityLevel.LOW,
                        time_window="full_period",
                        summary=summary,
                        supporting_metrics={"weekend_bias_percentage": weekend_bias},
                        confidence=0.82,
                        section="behavior"
                    )
                    insights.append(insight)
                    logger.debug(f"✅ Created insight: weekend_spending_bias")
        except Exception as e:
            logger.error(f"Error extracting behavioral insights: {e}", exc_info=True)
            errors.append(f"Behavioral insights extraction: {str(e)}")
    else:
        logger.warning("Behavioral analysis failed or returned no success flag")
        errors.append("Behavioral analysis failed")
    
    # ===== Merchant Insights =====
    if behavioral_data.get("success"):
        try:
            merchant_summary = behavioral_data["merchant_insights"]["data"]
            
            if merchant_summary:
                concentration = merchant_summary["concentration_metrics"]
                
                template = INSIGHT_TEMPLATES[InsightType.MERCHANT]["concentration_risk"]
                summary = template.format(
                    top_5_pct=f"{concentration['top_5_merchants_pct']:.1f}",
                    risk_level=concentration["concentration_risk"]
                )
                
                severity = SeverityLevel.HIGH if concentration["concentration_risk"] == "high" else \
                          SeverityLevel.MEDIUM if concentration["concentration_risk"] == "medium" else \
                          SeverityLevel.LOW
                
                insight = Insight(
                    insight_id="merchant_concentration_risk",
                    type=InsightType.MERCHANT,
                    severity=severity,
                    time_window="last_period",
                    summary=summary,
                    supporting_metrics=concentration,
                    confidence=0.90,
                    section="anomalies"
                )
                insights.append(insight)
                logger.debug(f"✅ Created insight: merchant_concentration_risk")
        except Exception as e:
            logger.error(f"Error extracting merchant insights: {e}", exc_info=True)
            errors.append(f"Merchant insights extraction: {str(e)}")
    
    # ===== Stability Insights =====
    trends_data = state.get("trends_insights", {})
    if trends_data.get("success"):
        try:
            stability_summary = trends_data["stability_profile"]["data"]
            
            if stability_summary:
                distribution = stability_summary["stability_distribution"]
                
                template = INSIGHT_TEMPLATES[InsightType.STABILITY]["predictability"]
                summary = template.format(
                    profile=stability_summary["insights"]["stability_profile"],
                    stable_pct=f"{distribution['stable_percentage']:.1f}",
                    volatile_pct=f"{distribution['volatile_percentage']:.1f}",
                    baseline_pct=f"{distribution['stable_percentage']:.1f}"
                )
                
                insight = Insight(
                    insight_id="spending_predictability",
                    type=InsightType.STABILITY,
                    severity=SeverityLevel.INFO,
                    time_window="full_period",
                    summary=summary,
                    supporting_metrics=distribution,
                    confidence=0.91,
                    section="trends"
                )
                insights.append(insight)
                logger.debug(f"✅ Created insight: spending_predictability")
        except Exception as e:
            logger.error(f"Error extracting stability insights: {e}", exc_info=True)
            errors.append(f"Stability insights extraction: {str(e)}")
    
    # ===== Anomaly Insights =====
    if behavioral_data.get("success") and state["config"].include_anomalies:
        try:
            anomaly_summary = behavioral_data["anomaly_insights"]["data"]
            
            # Check insights nested structure for total_anomalies
            total_anomalies = anomaly_summary.get("insights", {}).get("total_anomalies", 0)
            if anomaly_summary and total_anomalies > 0:
                anomaly_count = total_anomalies
                outliers = anomaly_summary.get("outlier_transactions", [])
                
                if outliers:
                    top_outlier = outliers[0]
                    template = INSIGHT_TEMPLATES[InsightType.ANOMALY]["outlier_detected"]
                    summary = template.format(
                        count=anomaly_count,
                        merchant=top_outlier["merchant"],
                        amount_formatted=f"${top_outlier['amount_abs']:.2f}",
                        std_dev=f"{top_outlier['z_score']:.1f}"
                    )
                    
                    insight = Insight(
                        insight_id="outlier_transactions_detected",
                        type=InsightType.ANOMALY,
                        severity=SeverityLevel.MEDIUM if anomaly_count > 5 else SeverityLevel.LOW,
                        time_window="last_period",
                        summary=summary,
                        supporting_metrics={
                            "anomaly_count": anomaly_count,
                            "top_outlier": top_outlier
                        },
                        confidence=0.79,
                        section="anomalies"
                    )
                    insights.append(insight)
                    logger.debug(f"✅ Created insight: outlier_transactions_detected")
        except Exception as e:
            logger.error(f"Error extracting anomaly insights: {e}", exc_info=True)
            errors.append(f"Anomaly insights extraction: {str(e)}")
    
    logger.info(f"📊 Aggregation complete: {len(insights)} insights generated, {len(errors)} errors")
    logger.debug(f"Insight IDs generated: {[i.insight_id for i in insights]}")
    
    return {
        "raw_insights": insights,
        "aggregation_errors": errors
    }


async def format_insights(state: InsightsState) -> Dict[str, Any]:
    """
    Format insights with optional LLM enrichment.
    
    - Always includes templated summaries (deterministic)
    - Optionally adds LLM narratives (if enabled in config)
    """
    logger.info(f"Formatting {len(state['raw_insights'])} insights...")
    
    formatted_insights: List[Insight] = []
    
    for insight in state["raw_insights"]:
        formatted_insight = insight.copy()
        
        # Add LLM narrative if enabled
        if state["config"].enable_llm_enrichment and state["config"].llm_model:
            try:
                llm_prompt = f"""
Based on this financial insight for a personal finance dashboard:

Type: {insight.type.value}
Summary: {insight.summary}
Metrics: {insight.supporting_metrics}

Provide a brief (1-2 sentences) personalized narrative analysis.
Focus on: 1) What this means, 2) Why it matters, 3) One actionable hint.
Keep it conversational and non-technical.
"""
                
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
