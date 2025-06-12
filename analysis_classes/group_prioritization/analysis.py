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
    STRATEGIC_ROLES
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

    def determine_strategic_role(self, brand_share: float, benchmark_share: float, 
                               brand_growth: float, benchmark_growth: float) -> str:
        """Determine strategic role based on share and growth comparison"""
        
        # If brand leads or matches benchmark with strong/stable performance
        if brand_share >= benchmark_share * 0.9:  # Within 10% of benchmark
            if brand_growth >= 0 or pd.isna(brand_growth):
                return STRATEGIC_ROLES.DEFEND_AND_LEAD.value
            else:
                return STRATEGIC_ROLES.AT_RISK.value
        
        # If brand is below benchmark but growing fast
        elif brand_share < benchmark_share and brand_growth > benchmark_growth:
            return STRATEGIC_ROLES.ACCELERATE_GROWTH.value
        
        # If brand underperforms in a valuable cocktail
        elif brand_share < benchmark_share * 0.5:  # Less than 50% of benchmark share
            return STRATEGIC_ROLES.FIX_AND_EXPAND.value
        
        # Default case - low relevance or declining category
        else:
            return STRATEGIC_ROLES.MONITOR_OR_DEPRIORITIZE.value

    def get_period_data(self, metrics: List[dict], period_filter: dict, other_filters: List[dict]) -> pd.DataFrame:
        """Pull all necessary data in one query with cocktail and brand as breakouts"""
        
        df = self.pull_data_func(
            metrics=metrics,
            breakouts=[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value, MenuColNames.BRAND_NAME_COL.value],
            filters=other_filters + [period_filter]
        )
        # TODO: drop None ingredient and brand names
        self.check_row_limit(df)
        
        return df

    # def get_cocktail_menu_placements(self, period_filter: dict) -> pd.DataFrame:
    #     df = self.pull_data_func(
    #         metrics=[{"name":"product_id", "label": "Product ID"}],
    #         breakouts=[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value],
    #         filters=[period_filter]
    #     )
    #     return df
    
    def process_period_data(self, df: pd.DataFrame, brand_name: str, benchmark_name: str) -> pd.DataFrame:
        """Process data for a single period to calculate placements and shares"""
        
        brand_col = MenuColNames.BRAND_NAME_COL.value
        cocktail_col = MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value
        
        brand_df = df[df[brand_col].str.lower() == brand_name.lower()]
        benchmark_df = df[df[brand_col].str.lower() == benchmark_name.lower()]

        cocktail_total_df = df.groupby(cocktail_col)['menu_placements'].sum().reset_index(name='cocktail_menu_placements')
        
        # Calculate shares
        brand_df = brand_df.merge(cocktail_total_df, on=cocktail_col, how='left')
        brand_df['brand_share'] = brand_df.apply(
            lambda row: self.calculate_share(row['menu_placements'], row['cocktail_menu_placements']), 
            axis=1
        )

        benchmark_df = benchmark_df.merge(cocktail_total_df, on=cocktail_col, how='left')
        benchmark_df['benchmark_share'] = benchmark_df.apply(
            lambda row: self.calculate_share(row['menu_placements'], row['cocktail_menu_placements']), 
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
        
        # cocktail_menu_placements_df = self.get_cocktail_menu_placements(current_period)
        
        current_data = self.get_period_data(parameters.metrics, current_period, [])
        brand_df_current, benchmark_df_current = self.process_period_data(current_data, brand_name, benchmark_name)
        
        if comparison_period:
            comparison_data = self.get_period_data(parameters.metrics, comparison_period, [])
            brand_df_comparison, benchmark_df_comparison = self.process_period_data(comparison_data, brand_name, benchmark_name)

            brand_df_comparison = brand_df_comparison.rename(columns={
                'brand_share': 'brand_share_prev',
                'cocktail_menu_placements': 'cocktail_menu_placements_prev',
                'menu_placements': 'menu_placements_prev'
            })
            
            benchmark_df_comparison = benchmark_df_comparison.rename(columns={
                'benchmark_share': 'benchmark_share_prev',
                'cocktail_menu_placements': 'cocktail_menu_placements_prev',
                'menu_placements': 'menu_placements_prev'
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
            brand_df['brand_growth_pp'] = (brand_df['brand_share'] - brand_df['brand_share_prev'])
            brand_df.drop(columns=['brand_share_prev', 'cocktail_menu_placements_prev', 'menu_placements_prev'], inplace=True)
            brand_df.rename(columns={
                'menu_placements': 'brand_menu_placements',
            }, inplace=True)

            benchmark_df['benchmark_growth_pp'] = (benchmark_df['benchmark_share'] - benchmark_df['benchmark_share_prev'])
            benchmark_df.drop(columns=['benchmark_share_prev', 'cocktail_menu_placements_prev', 'menu_placements_prev','cocktail_menu_placements'], inplace=True)
            benchmark_df.rename(columns={
                'menu_placements': 'benchmark_menu_placements',
            }, inplace=True)
        else:
            brand_df = brand_df_current
            benchmark_df = benchmark_df_current
        
        raw_comparison_df = brand_df.merge(benchmark_df, on=[cocktail_col], how='left')
        raw_comparison_df = raw_comparison_df[raw_comparison_df['ingredient_of_cocktail_name'] != "None"]
        cleaned_comparison_df = raw_comparison_df.dropna()

        # Determine strategic role
        cleaned_comparison_df['strategic_role'] = cleaned_comparison_df.apply(
            lambda row: self.determine_strategic_role(
                row['brand_share'], 
                row['benchmark_share'],
                row['brand_growth_pp'], 
                row['benchmark_growth_pp']
            ), 
            axis=1
        )
        
        return cleaned_comparison_df

    def format_table(self, df: pd.DataFrame, parameters: GroupPrioritizationParameters) -> pd.DataFrame:
        """Format the table with appropriate number formats"""
        
        formatted_df = pd.DataFrame()
        formatted_df['Cocktail'] = df[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value]
        formatted_df['Cocktail Menu Placements'] = df['cocktail_menu_placements'].apply(
            lambda x: self.helper.get_formatted_num(x, ',.0f')
        )

        formatted_df['Brand Menu Placements'] = df['brand_menu_placements'].apply(
            lambda x: self.helper.get_formatted_num(x, ',.0f')
        )
        formatted_df["Brand's Menu Share"] = df["brand_share"].apply(
            lambda x: self.helper.get_formatted_num(x, '.4%')
        )
        formatted_df["Brand's Menu Share Growth"] = df["brand_growth_pp"].apply(
            lambda x: self.helper.get_formatted_num(x, '.4pp')  # 4 decimal places for percentage points
        )


        formatted_df['Benchmark Brand Menu Placements'] = df['benchmark_menu_placements'].apply(
            lambda x: self.helper.get_formatted_num(x, ',.0f')
        )
        formatted_df["Benchmark Brand's Menu Share"] = df["benchmark_share"].apply(
            lambda x: self.helper.get_formatted_num(x, '.4%')
        )
        formatted_df["Benchmark Brand's Menu Share Growth"] = df["benchmark_growth_pp"].apply(
             lambda x: self.helper.get_formatted_num(x, '.4pp')  # 4 decimal places for percentage points
        )
        
        formatted_df["Strategic Role"] = df["strategic_role"]
        
        return formatted_df

    def get_facts_df(self, df_unformatted: pd.DataFrame) -> pd.DataFrame:
        """Create facts dataframe for insights using unformatted data"""
        
        facts = []
        
        # Group by Strategic Role and get top 3 cocktails for each role
        top_cocktails_by_role = []
        for role in df_unformatted['strategic_role'].unique():
            role_df = df_unformatted[df_unformatted['strategic_role'] == role]
            top_role_cocktails = role_df.nlargest(3, 'brand_menu_placements')
            top_cocktails_by_role.append(top_role_cocktails)    
        
        # Concatenate all top cocktails
        top_brand_cocktails = pd.concat(top_cocktails_by_role)
        
        # Create facts for each top cocktail
        for _, row in top_brand_cocktails.iterrows():
            facts.append({
                'Fact Type': f'Top {row["strategic_role"]} Cocktail',
                'Cocktail': row['ingredient_of_cocktail_name'],
                'Brand Share': row["brand_share"],
                'Brand Menu Placements': row["brand_menu_placements"],
                'Benchmark Brand Share': row["benchmark_share"],
                'Benchmark Brand Menu Placements': row["benchmark_menu_placements"],
                'Strategic Role': row['strategic_role']
            })
        
        return pd.DataFrame(facts)

    def get_title_and_subtitle(self, parameters: GroupPrioritizationParameters) -> Tuple[str, str]:
        """Generate title and subtitle for the analysis"""
        
        brand_name = parameters.brand_name
        benchmark_name = parameters.benchmark_brand
        period = parameters.period
        
        title = f"Group Prioritization: {brand_name} vs. {benchmark_name}"
               
        subtitle = old_get_date_label_str(parameters.date_labels, prefix="")
        if parameters.growth_type:
            subtitle = f"{subtitle} • {parameters.growth_type} Growth"
        
        return title, subtitle

    def run(self, parameters: GroupPrioritizationParameters) -> GroupPrioritizationRunResult:
        """Main execution method"""
        
        raw_comparison_df = self.build_comparison_table(parameters)
        comparison_df = raw_comparison_df.nlargest(parameters.limit_n, 'brand_menu_placements')
        comparison_df = self.format_table(comparison_df, parameters)

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
            export_data=[ExportData(name=name, data=df) for name, df in export_data.items()]
        )