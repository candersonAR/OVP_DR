from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from ar_analytics.defaults import SkillConfig, DEFAULT_MAX_PROMPT
from ar_analytics.helpers.utils import Connector
import pandas as pd
from skill_framework import ParameterDisplayDescription, SuggestedQuestion

from overproof_utilities import MenuColNames

group_prioritization_config = SkillConfig(
    name="Group Prioritization",
    llm_name="group_prioritization",
    description="""""",
    capabilities="""""",
    limitations="""Can only analyze one brand and one benchmark brand at a time.
""",
    example_questions="""""",
    parameter_guidance="""<TIME PERIODHANDLING>
- TIME PERIOD HANDLING: Use this section to better understand time periods for the 'periods' parameter selection: 
  - today is {{today}}. 
  - The data ends on {{copilot_dataset_end_date}}.
  -the latest period is the most recent full period in relation to the end of the data on {{copilot_dataset_end_date}}.
  - Phrases such as 'YTD', 'ytd', and 'this year' phrases result in time period analyses that end with the last date in the data. Prioritize the user's time period request when given. 
  -Phrases such as 'last X months' result in a time period analysis of X number of months of data ending with the last date in the data. 
  -For phrases requesting to compare 2 years or time periods, such as 'YYYY vs. YYYY', use the most recent YYYY as the 'period' parameter and add 'Y/Y' for the 'growth' parameter to show the comparison (vs.) to the previous year. 
  -If the user asks to compare 2 non-consecutive years, let them know you can only analyze consecutive time periods to show year-over-year (Y/Y) or period-over-period (P/P) growth. 
  -For phrases such as 'Last X months vs. last year',  let's break this down into 2 sections. ('last X months') and ('vs. last year'). Use ('last X months') as the time period and use (vs. last year) to add 'Y/Y' for the 'Growth' parameter. 
  - For phrases such as 'annual growth' show the MAT time period and set the 'growth' parameter to 'Y/Y'.
  - for phrases such as 'vs. YA', choose 'Y/Y' for the growth parameter. Set the period parameter to the baseline time period the user wishes to compare to.
- If no time period is provided, execute using skill default.
<TIME PERIODHANDLING>""",
    max_prompt=DEFAULT_MAX_PROMPT,
    insight_prompt="""Write a short headline followed by a 60 word or less paragraph about using facts below.
Use the structure from the 2 examples below to learn how I typically write summary.
Base your summary solely on the provided facts, avoiding assumptions or judgments.
Ensure clarity and accuracy.
Use markdown formatting for a structured and clear presentation.

Facts:
{{facts}}
Summary:"""
)


class GroupPrioritizationMetrics(Enum):
    COCKTAIL_MENU_PLACEMENTS = "cocktail_menu_placements"
    BRAND_MENU_PLACEMENTS = "brand_menu_placements"
    BRAND_MENU_SHARE = "brand_share"
    BRAND_MENU_SHARE_GROWTH = "brand_share_growth"
    BENCHMARK_MENU_PLACEMENTS = "benchmark_menu_placements"
    BENCHMARK_MENU_SHARE = "benchmark_share"
    BENCHMARK_MENU_SHARE_GROWTH = "benchmark_share_growth"
    STRATEGIC_ROLE = "strategic_role"

class STRATEGIC_ROLES(Enum):
    DEFEND_AND_LEAD = "Defend & Lead"
    PROTECT_POSITIONING = "Protect Positioning"
    INVEST_TO_GROW = "Invest to Grow"
    OPTIMIZE_OR_REPOSITION = "Optimize or Reposition"
    MONITOR_AND_NURTURE = "Monitor and Nurture"
    DEPRIORITIZE = "Deprioritize"

METRICS_MAPPING = {
    GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value: "Cocktail Menu Placements",
    GroupPrioritizationMetrics.BRAND_MENU_PLACEMENTS.value: "Brand Menu Placements",
    GroupPrioritizationMetrics.BRAND_MENU_SHARE.value: "Brand Menu Share",
    GroupPrioritizationMetrics.BRAND_MENU_SHARE_GROWTH.value: "Brand Menu Share Growth",
    GroupPrioritizationMetrics.BENCHMARK_MENU_PLACEMENTS.value: "Benchmark Menu Placements",
    GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE.value: "Benchmark Menu Share",
    GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE_GROWTH.value: "Benchmark Menu Share Growth",
    GroupPrioritizationMetrics.STRATEGIC_ROLE.value: "Strategic Role",
}

METRIC_INFO = {
    GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value: {
        "name": GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value,
        "label": METRICS_MAPPING[GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value],
        "sql": None,
        "col": None,
        "metric_type": None,
        "is_share": None,
        "is_growth": False,
        "growth_fmt": ",.2%",
        "fmt": ",.0f",
        "hide_percentage_change": False,
    },
    GroupPrioritizationMetrics.BRAND_MENU_PLACEMENTS.value: {
        "name": GroupPrioritizationMetrics.BRAND_MENU_PLACEMENTS.value,
        "label": METRICS_MAPPING[GroupPrioritizationMetrics.BRAND_MENU_PLACEMENTS.value],
        "sql": None,
        "col": None,
        "metric_type": None,
        "is_share": None,
        "is_growth": False,
        "growth_fmt": ",.2%",
        "fmt": ",.0f",
        "hide_percentage_change": False,
    },
    GroupPrioritizationMetrics.BRAND_MENU_SHARE.value: {
        "name": GroupPrioritizationMetrics.BRAND_MENU_SHARE.value,
        "label": METRICS_MAPPING[GroupPrioritizationMetrics.BRAND_MENU_SHARE.value],
        "component_metric": GroupPrioritizationMetrics.BRAND_MENU_SHARE.value,
        "sql": None,
        "col": None,
        "metric_type": "share",
        "is_share": True,
        "is_growth": False,
        "fmt": ",.3%",
        "growth_fmt": "bps",
        "hide_percentage_change": True,
    },
    GroupPrioritizationMetrics.BRAND_MENU_SHARE_GROWTH.value: {
        "name": GroupPrioritizationMetrics.BRAND_MENU_SHARE_GROWTH.value,
        "label": METRICS_MAPPING[GroupPrioritizationMetrics.BRAND_MENU_SHARE_GROWTH.value],
        "component_metric": GroupPrioritizationMetrics.BRAND_MENU_SHARE_GROWTH.value,
        "sql": None,
        "col": None,
        "metric_type": "share",
        "is_share": True,
        "is_growth": True,
        "fmt": ",.2%",
        "growth_fmt": ",.3pp",
        "hide_percentage_change": True,
    },
    GroupPrioritizationMetrics.BENCHMARK_MENU_PLACEMENTS.value: {
        "name": GroupPrioritizationMetrics.BENCHMARK_MENU_PLACEMENTS.value,
        "label": METRICS_MAPPING[GroupPrioritizationMetrics.BENCHMARK_MENU_PLACEMENTS.value],
        "sql": None,
        "col": None,
        "metric_type": None,
        "is_share": None,
        "is_growth": False,
        "growth_fmt": ",.2%",
        "fmt": ",.0f",
        "hide_percentage_change": False,
    },
    GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE.value: {
        "name": GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE.value,
        "label": METRICS_MAPPING[GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE.value],
        "component_metric": GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE.value,
        "sql": None,
        "col": None,
        "metric_type": "share",
        "is_share": True,
        "is_growth": False,
        "fmt": ",.3%",
        "growth_fmt": "bps",
        "hide_percentage_change": True,
    },
    GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE_GROWTH.value: {
        "name": GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE_GROWTH.value,
        "label": METRICS_MAPPING[GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE_GROWTH.value],
        "component_metric": GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE_GROWTH.value,
        "sql": None,
        "col": None,
        "metric_type": "share",
        "is_share": True,
        "is_growth": True,
        "fmt": ",.2%",
        "growth_fmt": ",.3pp",
        "hide_percentage_change": True,
    },
    GroupPrioritizationMetrics.STRATEGIC_ROLE.value: {
        "name": GroupPrioritizationMetrics.STRATEGIC_ROLE.value,
        "label": METRICS_MAPPING[GroupPrioritizationMetrics.STRATEGIC_ROLE.value],
        "sql": None,
        "col": None,
        "metric_type": None,
        "is_share": None,
        "is_growth": False,
        "fmt": ",.2f",
        "growth_fmt": ",.2f",
        "hide_percentage_change": False,
    },
}

DEFAULT_DIMENSIONS = [
    MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value,
]

DEFAULT_METRICS = [
    MenuColNames.MENU_PLACEMENTS_METRIC.value,
    MenuColNames.BRAND_NAME_COL.value,
]

DEFAULT_PERIOD = ["ytd"]
SIMILAR_SHARE_CUTOFF = 0.005
STAGNANT_GROWTH_THRESHOLD = 0.01

@dataclass
class GroupPrioritizationInit:
    sql_exec: Connector
    dim_hierarchy: dict
    compare_date_warning_msg: str
    pills: List[ParameterDisplayDescription]
    metric_props: dict
    dim_props: dict
    max_prompt: str
    insight_prompt: str
    table_viz_layout: str
    df_provider: Optional[object] = None

@dataclass
class GroupPrioritizationParameters:
    metrics: list[dict]
    dimensions: list[dict]
    brand_name: str
    benchmark_brand: str
    period: str
    period_filters: list[dict]
    other_filters: Optional[list[dict]] = None
    growth_type: Optional[str] = "Y/Y"  # Added with default
    date_labels: Optional[dict] = None  # Added
    limit_n: Optional[int] = 10

@dataclass
class GroupPrioritizationRunResult:
    table_df: pd.DataFrame
    fact_dfs: List[pd.DataFrame]
    followups: List[SuggestedQuestion]
    title: str
    subtitle: str
    warnings: Optional[str] = None
    general_footnote: Optional[str] = None