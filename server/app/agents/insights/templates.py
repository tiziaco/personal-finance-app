from app.schemas.insights import InsightType

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
