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

class MetricGroup(Enum):
    MENU_PLACEMENTS = "Cocktail Menu Placements"


DEFAULT_DIMENSIONS = [
    MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value,
]

DEFAULT_METRICS = [
  MenuColNames.MENU_PLACEMENTS_METRIC.value,
  MenuColNames.BRAND_NAME_COL.value,
]

DEFAULT_METRIC_GROUP_MAPPING = {
    MenuColNames.MENU_PLACEMENTS_METRIC.value: MetricGroup.MENU_PLACEMENTS.value,
}

DEFAULT_PERIOD = ["ytd"]


# TODO: Figure out what metric these roles are based on and what actual cutoffs are
class STRATEGIC_ROLES(Enum):
    DEFEND_AND_LEAD = "Defend & Lead"
    AT_RISK = "At Risk"
    ACCELERATE_GROWTH = "Accelerate Growth"
    FIX_AND_EXPAND = "Fix & Expand"
    MONITOR_OR_DEPRIORITIZE = "Monitor or Deprioritize"

# STRATEGIC_ROLES = {
#     "Defend & Lead" : 0.7,
#     "At Risk" : 0.5,    
#     "Accelerate Growth" : 0.3,
#     "Fix & Expand" : 0.1,
#     "Monitor or Deprioritize" : 0.0
# }

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

@dataclass
class GroupPrioritizationRunResult:
    table_df: pd.DataFrame
    fact_dfs: List[pd.DataFrame]
    followups: List[SuggestedQuestion]
    title: str
    subtitle: str
    warnings: Optional[str] = None
    general_footnote: Optional[str] = None