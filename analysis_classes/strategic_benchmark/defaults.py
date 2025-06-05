from dataclasses import dataclass
from typing import List, Optional
from ar_analytics.defaults import SkillConfig, DEFAULT_MAX_PROMPT
from ar_analytics.helpers.utils import Connector
import pandas as pd
from skill_framework import ParameterDisplayDescription, SuggestedQuestion

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
    insight_prompt=""""""
)


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
    metrics: list[str]
    subject_filter = dict
    peer_filters = list[dict]
    query_filters: Optional[list[dict]] = None
    period_filters: Optional[list[dict]] = None
    compare_date_warning_msg: Optional[str] = None
    date_labels: Optional[dict] = None

@dataclass
class StrategicBenchmarkRunResult:
    df: pd.DataFrame
    fact_dfs: List[pd.DataFrame]
    followups: List[SuggestedQuestion]