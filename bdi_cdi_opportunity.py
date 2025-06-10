from __future__ import annotations

import logging

from skill_framework import SkillInput, skill, SkillParameter
from ar_analytics.defaults import default_table_layout
from analysis_classes.bdi_cdi_opportunity.analysis import BdiCdiOpportunity
from analysis_classes.bdi_cdi_opportunity.template_parameter_setup import BdiCdiTemplateParameterSetup
from analysis_classes.bdi_cdi_opportunity.defaults import bdi_cdi_config
from overproof_data_provider import DataProvider
from overproof_utilities import MenuColNames

logger = logging.getLogger(__name__)

@skill(
    name=bdi_cdi_config.name,
    llm_name=bdi_cdi_config.llm_name,
    description=bdi_cdi_config.description,
    capabilities=bdi_cdi_config.capabilities,
    limitations=bdi_cdi_config.limitations,
    example_questions=bdi_cdi_config.example_questions,
    parameter_guidance=bdi_cdi_config.parameter_guidance,
    parameters=[
        SkillParameter(
            name="brand_filter",
            constrained_to=MenuColNames.BRAND_NAME_COL.value,
            description="Brand(s) to analyze",
            is_multi=True
        ),
        SkillParameter(
            name="category_filter",
            constrained_to=MenuColNames.PRODUCT_CATEGORY_NAME_COL.value,
            description="Category(s) to analyze",
            is_multi=True
        ),
        SkillParameter(
            name="breakout",
            description="Breakout dimension: 'state_name' or 'venue__county'"
        ),
        SkillParameter(
            name="periods",
            constrained_to="date_filter",
            is_multi=True,
            description="Time periods to include"
        ),
        SkillParameter(
            name="other_filters",
            constrained_to="filters",
            description="Additional filters"
        ),
        SkillParameter(
            name="max_prompt",
            parameter_type="prompt",
            description="Prompt being used for max response.",
            default_value=bdi_cdi_config.max_prompt
        ),
        SkillParameter(
            name="insight_prompt",
            parameter_type="prompt",
            description="Prompt being used for detailed insights.",
            default_value=bdi_cdi_config.insight_prompt
        ),
        SkillParameter(
            name="table_viz_layout",
            parameter_type="visualization",
            description="Table Viz Layout",
            default_value=default_table_layout
        )
    ]
)
def bdi_cdi_opportunity(parameters: SkillInput):
    init, params = BdiCdiTemplateParameterSetup().map_parameters(parameters=parameters)

    df_provider = DataProvider()
    init.df_provider = df_provider

    bdi_cdi = BdiCdiOpportunity(init=init)
    run_result = bdi_cdi.run(parameters=params)

    return bdi_cdi.create_viz(run_result=run_result)