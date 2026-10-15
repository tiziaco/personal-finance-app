"""Each response schema mirrors one domain result field for field; from_attributes would drop a field it lacks."""

from dataclasses import fields

import pytest

from app.modules.analytics import schemas
from app.modules.analytics.domain import anomalies, behaviour, categories, dashboard, merchants, recurring, spending

pytestmark = pytest.mark.unit

PAIRS = [
    (dashboard.CategorySlice, schemas.CategorySliceResponse),
    (dashboard.TrendPoint, schemas.TrendPointResponse),
    (dashboard.Dashboard, schemas.DashboardResponse),
    (spending.MonthFlow, schemas.MonthFlowResponse),
    (spending.SpendingSummary, schemas.SpendingResponse),
    (categories.CategorySpend, schemas.CategorySpendResponse),
    (categories.CategoryTrend, schemas.CategoryTrendResponse),
    (categories.CategoryBreakdown, schemas.CategoryBreakdownResponse),
    (merchants.MerchantSpend, schemas.MerchantSpendResponse),
    (merchants.MerchantConcentration, schemas.MerchantConcentrationResponse),
    (merchants.MerchantBreakdown, schemas.MerchantBreakdownResponse),
    (recurring.RecurringMerchant, schemas.RecurringMerchantResponse),
    (recurring.HiddenSubscription, schemas.HiddenSubscriptionResponse),
    (recurring.RecurringAnalysis, schemas.RecurringResponse),
    (behaviour.WeekdaySpend, schemas.WeekdaySpendResponse),
    (behaviour.WeekPart, schemas.WeekPartResponse),
    (behaviour.MonthOfYear, schemas.MonthOfYearResponse),
    (behaviour.CategoryStability, schemas.CategoryStabilityResponse),
    (behaviour.Behaviour, schemas.BehaviourResponse),
    (anomalies.Outlier, schemas.OutlierResponse),
    (anomalies.CategorySpike, schemas.CategorySpikeResponse),
    (anomalies.Anomalies, schemas.AnomaliesResponse),
]


def test_every_response_schema_is_paired():
    responses = {cls for name, cls in vars(schemas).items() if name.endswith("Response") and isinstance(cls, type)}
    assert responses == {schema for _, schema in PAIRS}


@pytest.mark.parametrize(("result", "schema"), PAIRS, ids=lambda cls: cls.__name__)
def test_schema_fields_match_the_domain_result(result, schema):
    assert [f.name for f in fields(result)] == list(schema.model_fields)
