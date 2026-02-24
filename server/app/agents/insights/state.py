from typing import Dict, Any, List, Optional

import polars as pl
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app.schemas.insights import Insight


class InsightsConfig(BaseModel):
    """Configuration for insights generation."""
    enable_llm_enrichment: bool = Field(default=False, description="Enable LLM narrative generation")
    llm_model: Optional[Any] = Field(default=None, description="LLM instance for narratives")
    time_window_days: int = Field(default=90, description="Default analysis window in days")
    min_confidence_score: float = Field(default=0.7, description="Min confidence for inclusion")
    include_anomalies: bool = Field(default=True, description="Include anomaly detection")
    anomaly_std_threshold: float = Field(default=2.5, description="Std deviations for anomalies")
    narrative_prompt_version: str = Field(default="v1", description="Prompt version for LLM narrative generation")


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
