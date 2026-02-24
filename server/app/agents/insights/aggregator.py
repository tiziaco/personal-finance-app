import logging
from typing import Dict, Any, List

from app.agents.insights.state import InsightsState
from app.agents.insights.templates import INSIGHT_TEMPLATES
from app.schemas.insights import Insight, InsightType, SeverityLevel

logger = logging.getLogger(__name__)


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
            spending_summary = spending_data["spending_summary"]
            category_insights = spending_data["category_insights"]
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
            recurring_summary = recurring_data["recurring_insights"]
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
            trend_summary = trends_data["trend_insights"]
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
            behavioral_summary = behavioral_data["behavioral_insights"]
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
            merchant_summary = behavioral_data["merchant_insights"]

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
            stability_summary = trends_data["stability_profile"]

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
            anomaly_summary = behavioral_data["anomaly_insights"]

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
