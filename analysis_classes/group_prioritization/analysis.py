from typing import List, Tuple
import pandas as pd
import numpy as np
from ar_analytics import pull_data
from ar_analytics.helpers.utils import old_get_filters_headline, old_get_date_label_str
from skill_framework import ExportData, SkillOutput

from analysis_classes.group_prioritization.defaults import (
    GroupPrioritizationInit, 
    GroupPrioritizationParameters, 
    GroupPrioritizationRunResult,
    STRATEGIC_ROLES,
    GroupPrioritizationMetrics,
    METRIC_INFO,
    SIMILAR_SHARE_CUTOFF,
    STAGNANT_GROWTH_THRESHOLD,
    COLUMN_ORDER
)
from overproof_utilities import MenuColNames, OverproofSharedFn
from overproof_visualization_utilities import render_layout

# Do not remove, pulls in max_metadata on all pandas DFs
import answer_rocket

class GroupPrioritization:
    def __init__(self, init: GroupPrioritizationInit):

        self.con = init.sql_exec
        self.dim_hierarchy = init.dim_hierarchy
        self.compare_date_warning_msg = init.compare_date_warning_msg
        self.pills = init.pills
        self.metric_props = init.metric_props
        self.dim_props = init.dim_props

        self.max_prompt = init.max_prompt
        self.insight_prompt = init.insight_prompt
        self.table_viz_layout = init.table_viz_layout

        self.pull_data_func = init.df_provider.pull_data if init.df_provider and hasattr(init.df_provider, "pull_data") else pull_data

        self.helper = OverproofSharedFn()
        self.notes = []
        self.hit_row_limit = False

    def check_row_limit(self, df: pd.DataFrame):
        if not self.hit_row_limit:
            self.hit_row_limit = len(df) == self.con.limit

    def get_warning_messages(self):
        warning_messages = []

        if self.hit_row_limit:
            msg = f'The following analysis has been limited to {self.helper.get_formatted_num(self.con.limit, ",.0f")} rows which may impact the accuracy of the observations made.'
            warning_messages.append(msg)

        if self.compare_date_warning_msg:
            warning_messages.append(self.compare_date_warning_msg)

        warning_message = ' '.join(warning_messages)
        if warning_message:
            warning_message = f"⚠ {warning_message}"

        return warning_message

    def calculate_share(self, numerator: float, denominator: float) -> float:
        """Calculate share, handling division by zero"""
        if denominator == 0 or pd.isna(denominator):
            return 0
        return (numerator / denominator)

    def calculate_growth(self, current: float, previous: float, is_share: bool = False) -> float:
        """Calculate growth - percentage points for shares, percentage for other metrics"""
        if pd.isna(previous) or previous == 0:
            return np.nan
        
        if is_share:
            return (current - previous)
        else:
            return (current - previous) / abs(previous)

    def determine_strategic_role(self, brand_menu_placements: float, brand_share: float,  brand_growth: float, 
                                benchmark_menu_placements: float, benchmark_share: float, benchmark_growth: float,
                               avg_placements_per_brand: float, avg_market_share: float) -> str:
        """Determine strategic role based on share and growth comparison"""
        
        # Brand is above average placements (Leading)
        if brand_menu_placements > avg_placements_per_brand:
            # Brand is similar to benchmark share
            if brand_share < benchmark_share + SIMILAR_SHARE_CUTOFF and brand_share > benchmark_share - SIMILAR_SHARE_CUTOFF:
                return STRATEGIC_ROLES.INVEST_TO_GROW.value                
                
            # Brand is above benchmark share
            elif brand_share >= benchmark_share:
                # Brand is stagnant
                if brand_growth >= -STAGNANT_GROWTH_THRESHOLD and brand_growth <= STAGNANT_GROWTH_THRESHOLD:
                    return STRATEGIC_ROLES.DEFEND_AND_LEAD.value
                
                # Brand is growing
                elif brand_growth >= STAGNANT_GROWTH_THRESHOLD:
                    return STRATEGIC_ROLES.PROTECT_POSITIONING.value
                
                # Brand is declining
                else:
                    return STRATEGIC_ROLES.DEFEND_AND_LEAD.value
            
            # Brand is below benchmark share (Lagging)
            else:
                # Brand is stagnant or declining
                if brand_growth <= STAGNANT_GROWTH_THRESHOLD:
                    return STRATEGIC_ROLES.OPTIMIZE_OR_REPOSITION.value
                
                # Brand is growing
                else:
                    return STRATEGIC_ROLES.INVEST_TO_GROW.value
                
                
        # Brand is below average placements (Lagging)
        else:
            # Brand is growing
            if brand_growth >= STAGNANT_GROWTH_THRESHOLD:
                return STRATEGIC_ROLES.MONITOR_AND_NURTURE.value
            
            # Brand is stagnant or declining
            else:
                return STRATEGIC_ROLES.DEPRIORITIZE.value
            
    def get_cocktail_placements(self, metrics: List[dict], period_filter: dict, other_filters: List[dict]) -> pd.DataFrame:
        
        df = self.pull_data_func(
            metrics=metrics,
            breakouts=[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value],
            filters=[period_filter]
        )
        self.check_row_limit(df)
        return df

    def get_brand_placements(self, metrics: List[dict], period_filter: dict, other_filters: List[dict]) -> pd.DataFrame:
        """Pull all necessary data in one query with cocktail and brand as breakouts"""
        
        df = self.pull_data_func(
            metrics=metrics,
            breakouts=[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value, MenuColNames.BRAND_NAME_COL.value],
            filters=other_filters + [period_filter]
        )
        # TODO: drop None ingredient and brand names
        self.check_row_limit(df)
        
        return df
    
    def process_period_data(self, cocktail_df: pd.DataFrame, df: pd.DataFrame, brand_name: str, benchmark_name: str) -> pd.DataFrame:
        """Process data for a single period to calculate placements and shares"""

        brand_col = MenuColNames.BRAND_NAME_COL.value
        cocktail_col = MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value
        
        brand_df = df[df[brand_col].str.lower() == brand_name.lower()]
        benchmark_df = df[df[brand_col].str.lower() == benchmark_name.lower()]

        grouped_by_cocktail = df.groupby(cocktail_col)
        brands_per_cocktail = grouped_by_cocktail[MenuColNames.BRAND_NAME_COL.value].nunique().reset_index(name="total_brands")
        
        cocktail_totals_df = cocktail_df.rename(columns={
            "menu_placements": GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value
        })
        cocktail_totals_df = cocktail_totals_df.merge(brands_per_cocktail, on=cocktail_col, how='left')
        cocktail_totals_df['avg_placements_per_brand'] = cocktail_totals_df[GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value] / cocktail_totals_df['total_brands']
        cocktail_totals_df['avg_market_share'] = 1 / cocktail_totals_df['total_brands']

        # Calculate shares
        brand_df = brand_df.merge(cocktail_totals_df, on=cocktail_col, how='left')
        brand_df[GroupPrioritizationMetrics.BRAND_MENU_SHARE.value] = brand_df.apply(
            lambda row: self.calculate_share(row['menu_placements'], row[GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value]), 
            axis=1
        )

        benchmark_df = benchmark_df.merge(cocktail_totals_df, on=cocktail_col, how='left')
        benchmark_df[GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE.value] = benchmark_df.apply(
            lambda row: self.calculate_share(row['menu_placements'], row[GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value]), 
            axis=1
        )
        
        return brand_df, benchmark_df

    def build_comparison_table(self, parameters: GroupPrioritizationParameters) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Build the main comparison table with all required columns. Returns (formatted_df, unformatted_df)"""
        
        # Extract parameters
        brand_name = parameters.brand_name
        benchmark_name = parameters.benchmark_brand
        current_period = parameters.period_filters[0]
        comparison_period = parameters.period_filters[1] if len(parameters.period_filters) > 1 else None
        
        current_cocktail_data = self.get_cocktail_placements(parameters.metrics, current_period, [])
        current_brand_data = self.get_brand_placements(parameters.metrics, current_period, [])
        brand_df_current, benchmark_df_current = self.process_period_data(current_cocktail_data, current_brand_data, brand_name, benchmark_name)
        
        if comparison_period:
            comparison_cocktail_data = self.get_cocktail_placements(parameters.metrics, comparison_period, [])
            comparison_brand_data = self.get_brand_placements(parameters.metrics, comparison_period, [])
            brand_df_comparison, benchmark_df_comparison = self.process_period_data(comparison_cocktail_data, comparison_brand_data, brand_name, benchmark_name)

            brand_df_comparison = brand_df_comparison.rename(columns={
                GroupPrioritizationMetrics.BRAND_MENU_SHARE.value: GroupPrioritizationMetrics.BRAND_MENU_SHARE.value + '_prev',
                GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value: GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value + '_prev',
                "menu_placements": 'menu_placements_prev',
                "avg_placements_per_brand": 'avg_placements_per_brand_prev',
                "avg_market_share": 'avg_market_share_prev'
            })
            
            benchmark_df_comparison = benchmark_df_comparison.rename(columns={
                GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE.value: GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE.value + '_prev',
                GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value: GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value + '_prev',
                "menu_placements": 'menu_placements_prev', 
                "avg_placements_per_brand": 'avg_placements_per_brand_prev',
                "avg_market_share": 'avg_market_share_prev'
            })
            
            cocktail_col = MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value
            brand_df = brand_df_current.merge(
                brand_df_comparison, 
                on=[cocktail_col, MenuColNames.BRAND_NAME_COL.value], 
                how='left'
            )
            
            benchmark_df = benchmark_df_current.merge(
                benchmark_df_comparison, 
                on=[cocktail_col, MenuColNames.BRAND_NAME_COL.value], 
                how='left'
            )
            benchmark_df = benchmark_df.rename(columns={
                'brand_name': 'benchmark_brand_name',
            })
            
            # Calculate growth (in basis points for shares)
            brand_df[GroupPrioritizationMetrics.BRAND_MENU_SHARE_GROWTH.value] = (brand_df[GroupPrioritizationMetrics.BRAND_MENU_SHARE.value] - brand_df[GroupPrioritizationMetrics.BRAND_MENU_SHARE.value + '_prev'])
            brand_cols_to_drop = [
                                    GroupPrioritizationMetrics.BRAND_MENU_SHARE.value + '_prev', 
                                    GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value + '_prev', 
                                    'menu_placements_prev',
                                    'avg_placements_per_brand_prev',
                                    'avg_market_share_prev'
            ]
            brand_df.drop(columns=brand_cols_to_drop, inplace=True)
            brand_df.rename(columns={
                'menu_placements': GroupPrioritizationMetrics.BRAND_MENU_PLACEMENTS.value,
            }, inplace=True)


            benchmark_df[GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE_GROWTH.value] = (benchmark_df[GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE.value] - benchmark_df[GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE.value + '_prev'])
            benchmark_cols_to_drop = [
                                        GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE.value + '_prev', 
                                        GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value + '_prev',
                                        GroupPrioritizationMetrics.COCKTAIL_MENU_PLACEMENTS.value,
                                        'menu_placements_prev',
                                        'avg_placements_per_brand',
                                        'avg_placements_per_brand_prev',
                                        'avg_market_share',
                                        'avg_market_share_prev'
            ]
            benchmark_df.drop(columns=benchmark_cols_to_drop, inplace=True)
            benchmark_df.rename(columns={
                'menu_placements': GroupPrioritizationMetrics.BENCHMARK_MENU_PLACEMENTS.value,
            }, inplace=True)
        else:
            brand_df = brand_df_current
            benchmark_df = benchmark_df_current
        
        raw_comparison_df = brand_df.merge(benchmark_df, on=[cocktail_col], how='left')
        raw_comparison_df = raw_comparison_df[raw_comparison_df[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value] != "None"]
        cleaned_comparison_df = raw_comparison_df.dropna()

        # Determine strategic role
        cleaned_comparison_df[GroupPrioritizationMetrics.STRATEGIC_ROLE.value] = cleaned_comparison_df.apply(
            lambda row: self.determine_strategic_role(
                row[GroupPrioritizationMetrics.BRAND_MENU_PLACEMENTS.value],
                row[GroupPrioritizationMetrics.BRAND_MENU_SHARE.value], 
                row[GroupPrioritizationMetrics.BRAND_MENU_SHARE_GROWTH.value], 
                row[GroupPrioritizationMetrics.BENCHMARK_MENU_PLACEMENTS.value],
                row[GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE.value],
                row[GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE_GROWTH.value],
                row['avg_placements_per_brand'],
                row['avg_market_share']
            ), 
            axis=1
        )

        cols_to_drop = [
            'total_brands_x_x',
            'total_brands_x_y',
            'total_brands_y_x',
            'total_brands_y_y',
            'avg_placements_per_brand',
            'avg_market_share',
            'brand_name',
            'benchmark_brand_name'
        ]
        cleaned_comparison_df.drop(columns=cols_to_drop, inplace=True)
        
        return cleaned_comparison_df

    def format_table(self, df: pd.DataFrame) -> pd.DataFrame:
        """Format the table with appropriate number formats"""
        metric_props = self.metric_props.copy()
        metric_props.update(METRIC_INFO)


        formatted_df = pd.DataFrame()
        for metric in df.columns:
            metric_prop = self.helper.get_metric_prop(metric, metric_props)
            if "is_growth" in metric_prop and metric_prop['is_growth']:
                formatted_df[metric_prop['label']] = df[metric].apply(
                    lambda x: self.helper.get_formatted_num(x, metric_prop['growth_fmt'])
                )
            else:
                formatted_df[metric_prop['label']] = df[metric].apply(
                    lambda x: self.helper.get_formatted_num(x, metric_prop['fmt'])
                )
        
        return formatted_df

    def get_facts_df(self, df_unformatted: pd.DataFrame) -> pd.DataFrame:
        """Create facts dataframe for insights using unformatted data"""
        
        facts = []
        
        # Group by Strategic Role and get top 3 cocktails for each role
        top_cocktails_by_role = []
        for role in df_unformatted[GroupPrioritizationMetrics.STRATEGIC_ROLE.value].unique():
            role_df = df_unformatted[df_unformatted[GroupPrioritizationMetrics.STRATEGIC_ROLE.value] == role]
            top_role_cocktails = role_df.nlargest(3, GroupPrioritizationMetrics.BRAND_MENU_PLACEMENTS.value)
            top_cocktails_by_role.append(top_role_cocktails)    
        
        # Concatenate all top cocktails
        top_brand_cocktails = pd.concat(top_cocktails_by_role)
        
        # Create facts for each top cocktail
        for _, row in top_brand_cocktails.iterrows():
            facts.append({
                'Fact Type': f'Top {row[GroupPrioritizationMetrics.STRATEGIC_ROLE.value]} Cocktail',
                'Cocktail': row[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value],
                'Brand Share': row[GroupPrioritizationMetrics.BRAND_MENU_SHARE.value],
                'Brand Menu Placements': row[GroupPrioritizationMetrics.BRAND_MENU_PLACEMENTS.value],
                'Brand Menu Share Growth': row[GroupPrioritizationMetrics.BRAND_MENU_SHARE_GROWTH.value],
                'Benchmark Brand Share': row[GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE.value],
                'Benchmark Brand Menu Placements': row[GroupPrioritizationMetrics.BENCHMARK_MENU_PLACEMENTS.value],
                'Benchmark Brand Menu Share Growth': row[GroupPrioritizationMetrics.BENCHMARK_MENU_SHARE_GROWTH.value],
                'Strategic Role': row[GroupPrioritizationMetrics.STRATEGIC_ROLE.value]
            })
        
        return pd.DataFrame(facts)

    def get_title_and_subtitle(self, parameters: GroupPrioritizationParameters) -> Tuple[str, str]:
        """Generate title and subtitle for the analysis"""
        
        brand_name = parameters.brand_name
        benchmark_name = parameters.benchmark_brand
        
        title = f"Group Prioritization: {brand_name} vs. {benchmark_name}"
               
        subtitle = old_get_date_label_str(parameters.date_labels, prefix="")
        if parameters.growth_type:
            subtitle = f"{subtitle} • {parameters.growth_type} Growth"
        
        return title, subtitle

    def run(self, parameters: GroupPrioritizationParameters) -> GroupPrioritizationRunResult:
        """Main execution method"""
        
        raw_comparison_df = self.build_comparison_table(parameters)
        comparison_df = raw_comparison_df.nlargest(parameters.limit_n, GroupPrioritizationMetrics.BRAND_MENU_PLACEMENTS.value)
        comparison_df = self.format_table(comparison_df)
        comparison_df = comparison_df[COLUMN_ORDER]
        
        facts_df = self.get_facts_df(raw_comparison_df)
        
        title, subtitle = self.get_title_and_subtitle(parameters)
        
        warnings = self.get_warning_messages()
        
        self.notes.append(f"Analysis compares {parameters.brand_name} performance against {parameters.benchmark_brand} across cocktails.")
        self.notes.append("Menu placements calculated as count of distinct products per cocktail.")
        if len(parameters.period_filters) > 1:
            self.notes.append(f"Growth calculated as {parameters.growth_type} change in menu share (basis points).")
        
        result = GroupPrioritizationRunResult(
            table_df=comparison_df,
            fact_dfs=[facts_df, pd.DataFrame({'Note to the assistant:': self.notes})],
            followups=[],
            title=title,
            subtitle=subtitle,
            warnings=warnings
        )
        
        return result

    def create_viz(self, run_result: GroupPrioritizationRunResult) -> SkillOutput:
        """Create visualization output"""
        
        tables = {run_result.title: run_result.table_df}
        warnings = run_result.warnings
        footnotes = {}
        general_footnote = run_result.general_footnote

        viz, insights, final_prompt, export_data = render_layout(
            tables,
            run_result.title,
            run_result.subtitle,
            run_result.fact_dfs,
            warnings,
            footnotes,
            general_footnote,
            self.max_prompt,
            self.insight_prompt,
            self.table_viz_layout
        )

        return SkillOutput(
            final_prompt=final_prompt,
            narrative=None,
            visualizations=viz,
            parameter_display_descriptions=self.pills,
            followup_questions=run_result.followups,
            export_data=[ExportData(name=name, id=df.max_metadata.get_id(), data=df) for name, df in export_data.items()]
        )