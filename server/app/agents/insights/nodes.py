import logging
from typing import Dict, Any

from app.agents.insights.state import InsightsState
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

logger = logging.getLogger(__name__)


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

        category_insights = await get_category_insights(
            state["transactions_df"],
            start_date=state["start_date"],
            end_date=state["end_date"]
        )

        return {
            "spending_insights": {
                "spending_summary": spending_summary,
                "category_insights": category_insights,
                "success": True,
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

        return {
            "recurring_insights": {
                "recurring_insights": recurring_insights,
                "success": True,
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

        stability_profile = await get_spending_stability_profile(
            state["transactions_df"],
            start_date=state["start_date"],
            end_date=state["end_date"]
        )

        return {
            "trends_insights": {
                "trend_insights": trend_insights,
                "stability_profile": stability_profile,
                "success": True,
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

        merchant_insights = await get_merchant_insights(
            state["transactions_df"],
            start_date=state["start_date"],
            end_date=state["end_date"]
        )

        anomaly_insights = None
        if state["config"].include_anomalies:
            anomaly_insights = await get_anomaly_insights(
                state["transactions_df"],
                start_date=state["start_date"],
                end_date=state["end_date"],
                std_threshold=state["config"].anomaly_std_threshold
            )

        return {
            "behavioral_anomaly_insights": {
                "behavioral_insights": behavioral_patterns,
                "merchant_insights": merchant_insights,
                "anomaly_insights": anomaly_insights,
                "success": True,
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
