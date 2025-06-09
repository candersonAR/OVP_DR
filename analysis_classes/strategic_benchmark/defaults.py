from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from ar_analytics.defaults import SkillConfig, DEFAULT_MAX_PROMPT
from ar_analytics.helpers.utils import Connector
import pandas as pd
from skill_framework import ParameterDisplayDescription, SuggestedQuestion

from overproof_utilities import MenuColNames

strategic_benchmark_config = SkillConfig(
    name="Strategic Benchmark",
    llm_name="strategic_benchmark",
    description="""""",
    capabilities="""""",
    limitations="""Can only analyze one subject at a time, which must be either a brand or a product.
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

class StrategicBenchmarkCustomMetrics(Enum):
    COCKTAIL_MENTIONS = "cocktail_mentions"
    SINGLE_SPIRIT_MENTIONS = "single_spirit_mentions"
    AVERAGE_MONTHLY_MENTIONS = "average_monthly_mentions"

STRAGEGIC_BENCHMARK_CUSTOM_METRIC_PROPS = {
    StrategicBenchmarkCustomMetrics.COCKTAIL_MENTIONS.value: {
        "name": StrategicBenchmarkCustomMetrics.COCKTAIL_MENTIONS.value,
        "label": "Cocktail Mentions"
    },
    StrategicBenchmarkCustomMetrics.SINGLE_SPIRIT_MENTIONS.value: {
        "name": StrategicBenchmarkCustomMetrics.SINGLE_SPIRIT_MENTIONS.value,
        "label": "Single Spirit Mentions"
    },
    StrategicBenchmarkCustomMetrics.AVERAGE_MONTHLY_MENTIONS.value: {
        "name": StrategicBenchmarkCustomMetrics.AVERAGE_MONTHLY_MENTIONS.value,
        "label": "Average Monthly Mentions",
        "fmt": ",.2f"
    }
}

class MetricGroup(Enum):
    MENU_PRESENCE = "Menu Presence"
    VENUE_PRESENCE = "Venue Presence"
    GEOGRAPHICAL_EXPANSION = "Geographical Expansion"
    VELOCITY = "Velocity"
    MARKET_SHARE_AND_PLACEMENT_HEALTH = "Market Share & Placement Health"

DEFAULT_METRICS = [
    MenuColNames.MENU_PLACEMENTS_METRIC.value, 
    StrategicBenchmarkCustomMetrics.COCKTAIL_MENTIONS.value,
    StrategicBenchmarkCustomMetrics.SINGLE_SPIRIT_MENTIONS.value,
    MenuColNames.VENUE_PLACEMENTS_METRIC.value,
    MenuColNames.STATE_MENTIONS_METRIC.value,
    MenuColNames.POSTAL_CODE_MENTIONS_METRIC.value,
    StrategicBenchmarkCustomMetrics.AVERAGE_MONTHLY_MENTIONS.value,
    MenuColNames.MENU_PLACEMENTS_SHARE_METRIC.value
]

DEFAULT_METRIC_GROUP_MAPPING = {
    MenuColNames.VENUE_PLACEMENTS_METRIC.value: MetricGroup.VENUE_PRESENCE.value,
    MenuColNames.MENU_PLACEMENTS_METRIC.value: MetricGroup.MENU_PRESENCE.value,
    StrategicBenchmarkCustomMetrics.COCKTAIL_MENTIONS.value: MetricGroup.MENU_PRESENCE.value,
    StrategicBenchmarkCustomMetrics.SINGLE_SPIRIT_MENTIONS.value: MetricGroup.MENU_PRESENCE.value,
    MenuColNames.STATE_MENTIONS_METRIC.value: MetricGroup.GEOGRAPHICAL_EXPANSION.value,
    MenuColNames.POSTAL_CODE_MENTIONS_METRIC.value: MetricGroup.GEOGRAPHICAL_EXPANSION.value,
    StrategicBenchmarkCustomMetrics.AVERAGE_MONTHLY_MENTIONS.value: MetricGroup.VELOCITY.value,
    MenuColNames.MENU_PLACEMENTS_SHARE_METRIC.value: MetricGroup.MARKET_SHARE_AND_PLACEMENT_HEALTH.value
}

@dataclass
class StrategicBenchmarkInit:
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
class StrategicBenchmarkParameters:
    metrics: list[dict]
    subject_filter: dict
    peer_filters: list[dict]
    query_filters: Optional[list[dict]] = None
    period_filters: Optional[list[dict]] = None
    compare_date_warning_msg: Optional[str] = None
    date_labels: Optional[dict] = None
    growth_type: Optional[str] = "Y/Y"

@dataclass
class StrategicBenchmarkRunResult:
    table_df: pd.DataFrame
    fact_dfs: List[pd.DataFrame]
    followups: List[SuggestedQuestion]
    title: str
    subtitle: str
    warnings: Optional[str] = None
    general_footnote: Optional[str] = None