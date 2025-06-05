from __future__ import annotations

from skill_framework import SkillInput, skill, SkillParameter

from ar_analytics.defaults import default_table_layout
from analysis_classes.strategic_benchmark.analysis import StrategicBenchmark
from analysis_classes.strategic_benchmark.template_parameter_setup import StrategicBenchmarkTemplateParameterSetup
from analysis_classes.strategic_benchmark.defaults import strategic_benchmark_config
from overproof_data_provider import DataProvider

import logging

logger = logging.getLogger(__name__)

@skill(
    name=strategic_benchmark_config.name,
    llm_name=strategic_benchmark_config.llm_name,
    description=strategic_benchmark_config.description,
    capabilities=strategic_benchmark_config.capabilities,
    limitations=strategic_benchmark_config.limitations,
    example_questions=strategic_benchmark_config.example_questions,
    parameter_guidance=strategic_benchmark_config.parameter_guidance,
    parameters=[
        SkillParameter(
            name="periods",
            constrained_to="date_filter",
            is_multi=True,
            description="If provided by the user, list time periods in a format 'q2 2023', '2021', 'jan 2023', 'mat nov 2022', 'mat q1 2021', 'ytd q4 2022', 'ytd 2023', 'ytd', 'mat', '<no_period_provided>' or '<since_launch>'. Use knowledge about today's date to handle relative periods and open ended periods. If given a range, for example 'last 3 quarters, 'between q3 2022 to q4 2023' etc, enumerate the range into a list of valid dates. Don't include natural language words or phrases, only valid dates like 'q3 2023', '2022', 'mar 2020', 'ytd sep 2021', 'mat q4 2021', 'ytd q1 2022', 'ytd 2021', 'ytd', 'mat', '<no_period_provided>' or '<since_launch>' etc."
        ),
        SkillParameter(
            name="other_filters",
            constrained_to="filters"
        ),
        SkillParameter(
            name="max_prompt",
            parameter_type="prompt",
            description="Prompt being used for max response.",
            default_value=strategic_benchmark_config.max_prompt
        ),
        SkillParameter(
            name="insight_prompt",
            parameter_type="prompt",
            description="Prompt being used for detailed insights.",
            default_value=strategic_benchmark_config.insight_prompt
        ),
        SkillParameter(
            name="table_viz_layout",
            parameter_type="visualization",
            description="Table Viz Layout",
            default_value=default_table_layout
        )
    ]
)
def strategic_benchmark(parameters: SkillInput):

    init, sb_parameters = StrategicBenchmarkTemplateParameterSetup().map_parameters(parameters=parameters)

    df_provider = DataProvider()
    init.df_provider = df_provider

    sb = StrategicBenchmark(init=init)  

    sb_result = sb.run(parameters=sb_parameters)
    return sb.create_viz(run_result=sb_result)