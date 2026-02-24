"""Unit tests for the Insight DB model."""


def test_insight_model_has_required_fields():
    from app.models.insight import Insight

    fields = Insight.model_fields
    assert "user_id" in fields
    assert "insights" in fields
    assert "generated_at" in fields


def test_insight_model_is_table():
    from app.models.insight import Insight

    assert hasattr(Insight, "__tablename__")
    assert Insight.__tablename__ == "insight"
