from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
import pandas as pd
from ar_analytics.defaults import SkillConfig, DEFAULT_MAX_PROMPT
from ar_analytics.helpers.utils import Connector
from skill_framework import ParameterDisplayDescription, SuggestedQuestion
from overproof_utilities import MenuColNames
from analysis_classes.strategic_benchmark.defaults import strategic_benchmark_config

bdi_cdi_config = SkillConfig(
    name="BDI/CDI Opportunity",
    llm_name="bdi_cdi_opportunity",
    description="Identify geographic markets where a brand is underperforming relative to category strength — helping prioritize state/county-level expansion, defend existing strongholds, and eliminate low-ROI push zones.",
    capabilities="Compute Brand Development Index (BDI), Category Development Index (CDI), Opportunity Score, Brand Share, and Category Share for each market.",
    limitations="Must provide both brand and category filters.",
    example_questions="Where are the BDI/CDI opportunities for Chocapic within its category?",
    parameter_guidance="""
Use brand_filter and category_filter to specify the brand and category of interest.
The breakout parameter accepts 'state_name' or 'venue__county'.
The periods parameter uses standard date handling (e.g., 'MAT Q1 2023', 'Q4 2022').
""",
    max_prompt=DEFAULT_MAX_PROMPT,
    insight_prompt=strategic_benchmark_config.insight_prompt
)

@dataclass
class BdiCdiInit:
    sql_exec: Connector
    dim_hierarchy: dict
    pills: List[ParameterDisplayDescription]
    metric_props: dict
    dim_props: dict
    max_prompt: str
    insight_prompt: str
    table_viz_layout: str
    df_provider: Optional[object] = None

@dataclass
class BdiCdiParameters:
    brand_filter: str
    category_filter: str
    breakout: str
    other_filters: Optional[List[dict]]
    period_filters: Optional[List[dict]]
    date_labels: Optional[dict]

@dataclass
class BdiCdiRunResult:
    table_df: pd.DataFrame
    fact_dfs: List[pd.DataFrame]
    followups: List[SuggestedQuestion]
    title: str
    subtitle: str
    warnings: Optional[str] = None
    general_footnote: Optional[str] = None
  
class FactColumnFormat(Enum):  # Define formats for fact columns
    BDI = ("BDI", ",.2f", False)
    CDI = ("CDI", ",.2f", False)
    OPPORTUNITY_SCORE = ("opportunity_score", ",.2f", True)
    BRAND_SHARE = ("brand_share", ",.2%", False)
    CATEGORY_SHARE = ("category_share", ",.2%", False)

    def __init__(self, col_name: str, fmt: str, signed: bool):
        self.col_name = col_name
        self.fmt = fmt
        self.signed = signed