import ast
import re

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from simpleeval import DEFAULT_FUNCTIONS, EvalWithCompoundTypes

from ar_analytics.helpers.utils import MetricTree, SharedFn, Connector, \
    exit_with_status, is_using_max_sql_gen, pull_data

from temp_util import sparkline

class ImpactCalculator:
    def __init__(self):
        self.delta_func = 'delta'
        self.prior_func = 'prior'
        self.curr_func = 'current'


    def extract_formula_terms(self, original_formula, coalesce_on_dots=True):
        class Analyzer(ast.NodeVisitor):
            def __init__(self):
                self.ids = []

            def generic_visit(self, node):

                if type(node) == ast.Name:
                    self.ids.append(node.id)
                elif type(node) == ast.Str:
                    self.ids.append(node.s)
                elif type(node) == ast.Attribute:
                    self.ids.append(node.attr)

                ast.NodeVisitor.generic_visit(self, node)

        formula = self.senitize_formula(original_formula)
        analyzer = Analyzer()
        sanitized_formula = formula.replace(".", "__") if coalesce_on_dots else formula
        analyzer.visit(ast.parse(sanitized_formula))

        ret = []
        metric_prefixes = ['current', 'prior', 'delta', 'root_impact', 'parent_impact']
        functions = ['boost', 'round', 'abs', 'mix_effect', 'regression']

        for token in analyzer.ids:
            if token not in ret:
                if token in functions:
                    continue

                if coalesce_on_dots:
                    for prefix in metric_prefixes:
                        if token.startswith(prefix + "__"):
                            full_prefix_len = len(prefix) + 2
                            ret.append(token[full_prefix_len:])
                            break
                    else:
                        ret.append(token)
                else:
                    if token not in ret and token not in metric_prefixes:
                        ret.append(token)

        out_list = [s.replace("__", ".") for s in ret] if coalesce_on_dots else ret
        return list(set(out_list))

    def get_component_metrics(self, expr_dict):
        comp_mets = []
        for _, expr in expr_dict.items():
            try:
                comp_mets.extend(self.extract_formula_terms(expr))
            except:
                continue
        return list(set(comp_mets))

    def senitize_formula(self, formula):
        def func_pattern(pattern):
            return f"{pattern.group(1)}.{pattern.group(2).strip(' []()<>')}"

        def senitize_string(term):
            term = str(term).strip("<>").strip().lower().replace(" ", "_")
            return term

        formula = re.sub(r"<\s*([^']*?)\s*>",  lambda m: senitize_string(m.group()), formula)

        for func_names in [self.delta_func , self.prior_func, self.curr_func]:
            formula = re.sub(rf"({func_names})\((\s*([^']*?)\s*)\)",  lambda m: func_pattern(m), formula)

        return formula

    def eval_formula(self, expr, names=None):
        functions_list = DEFAULT_FUNCTIONS.copy()
        functions_list.update(abs=abs)
        functions_list.update(round=round)
        s = EvalWithCompoundTypes(functions=functions_list, names=names)
        return s.eval(expr)

    def calculate_impacts(self, data_df, expr_dict):
        df = data_df.copy(deep=True)
        data_dict = {self.delta_func: df.loc[:, 'diff'].to_dict(),
                     self.prior_func: df.loc[:, 'prev'].to_dict(),
                     self.curr_func: df.loc[:, 'curr'].to_dict()}
        impacts = {}
        for kpi, expr in expr_dict.items():
            try:
                formula = self.senitize_formula(expr)
                impact = self.eval_formula(formula, names=data_dict)
            except:
                impact = np.nan

            impacts[kpi] = impact

        return impacts

class MetricTreeAnalysis:
    def __init__(self, sql_exec:Connector=None, df_provider=None, sp=None):
        self.metric_tree = None

        self.pull_data_func = df_provider.pull_data if df_provider and hasattr(df_provider, "pull_data") else pull_data

        self.sp = sp

        self.use_max_sql_gen = is_using_max_sql_gen()

        # database connection
        if sql_exec:
            self.con = sql_exec
        else:
            raise exit_with_status("sql_exec is required. Please use a Connector of type 'duckdb', 'parquet', or 'db'.")

        self.helper = SharedFn()
        self.ic = ImpactCalculator()
        self.impact_df_col = "impact"

    def _get_metric_growth(self, table, metrics, period_filters, query_filters, table_specific_filters, view=""):
        additional_filters = table_specific_filters.get('default', [])

        df_curr = self.pull_data_func(metrics=metrics, filters=query_filters+additional_filters+[period_filters[0]])
        df_prev = self.pull_data_func(metrics=metrics, filters=query_filters+additional_filters+[period_filters[1]])

        df_curr = df_curr.T
        df_prev = df_prev.T
        df = pd.concat([df_curr, df_prev], axis=1)

        df.index.name = 'metric'
        df.columns = ['curr', 'prev']

        # convert curr and prev to float
        df['curr'] = df['curr'].astype(float)
        df['prev'] = df['prev'].astype(float)

        df['diff'] = df['curr'] - df['prev']
        df['growth'] = df['diff'].div(np.abs(df['prev'].replace(0, np.nan)), fill_value=0)

        return df

    def combine_metric_tree(self, metric_df, target_metric, driver_metrics):
        self.metric_tree = MetricTree(target_metric, driver_metrics)

        # case insensitive merge, but keeps the casing of the metric_df index
        metric_names = metric_df.index
        metric_df = pd.merge(metric_df, self.metric_tree.df, left_on=metric_df.index.str.lower(), right_on=self.metric_tree.df["metric"].str.lower(), how="left")
        metric_df.index = metric_names
        metric_df.drop(columns=['key_0', 'metric'], inplace=True)

        # order dataframe based on child-parent relationship
        def order_df(df, parent=None):
            ordered_df = pd.DataFrame()
            if parent is None:
                base_rows = df[df['parent_metric'].isnull()]
            else:
                base_rows = df[df['parent_metric'] == parent]

            for _, row in base_rows.iterrows():
                # Use pd.concat instead of append
                ordered_df = pd.concat([ordered_df, pd.DataFrame([row])])
                # Recursively process child rows
                children_df = order_df(df, parent=row.name)
                ordered_df = pd.concat([ordered_df, children_df])

            return ordered_df

        metric_df = order_df(metric_df)

        return metric_df

    def _add_sparklines(self, metric_df, table, metrics, period_filters, query_filters, table_specific_filters, period_col_granularity, two_year_filter=None, view=""):


        if two_year_filter:
            period_filter = two_year_filter
            period_col = period_filter['col']
        else:
            # first period filter must be current period
            if period_filters[0]['op'].lower() == 'between':
                curr_period = period_filters[0]['val'].lower().split(' and ')[1]
            else:
                curr_period = period_filters[0]['val']
            period_col = period_filters[0]['col']

            granularity_to_format = {
                'year': '%Y',
                'month': '%Y-%m',
                'day': '%Y-%m-%d'
            }
            trend_timedelta = relativedelta(years=2)
            start_period = (pd.to_datetime(curr_period) - trend_timedelta).strftime( granularity_to_format[period_col_granularity])
            if not curr_period.startswith("'"):
                curr_period = f"'{curr_period}'"
            period_filter = {"col": period_col, "op": "BETWEEN", "val": f"'{start_period}' AND {curr_period}"}

        additional_filters = table_specific_filters.get('default', [])

        # create sparklines for each metric
        metric_trend_df = self.pull_data_func(metrics=metrics, breakouts=[period_col], filters=query_filters+additional_filters+[period_filter], order_cols=[{"col": period_col, "direction": "ASC"}])
        if not metric_trend_df.empty:
            metric_df['sparkline'] = metric_df.index.to_series().apply(lambda x: sparkline(metric_trend_df[x].to_list()) if x in metric_trend_df else sparkline([np.nan]))

        return metric_df

    def apply_metric_tree_formatting(self, df: pd.DataFrame, metric_props={}):

        df = df.reset_index().rename(columns={'index': 'metric'})
        if 'sparkline' in df.columns:
            df = df.drop('sparkline', axis=1)

        df['curr'] = df.apply(lambda x: self.helper.get_formatted_num(x['curr'], self.helper.get_metric_prop(x['metric'], metric_props)['fmt']), axis=1)
        df['prev'] = df.apply(lambda x: self.helper.get_formatted_num(x['prev'], self.helper.get_metric_prop(x['metric'], metric_props)['fmt']), axis=1)
        df['diff'] = df.apply(lambda x: self.helper.get_formatted_num(x['diff'], self.helper.get_metric_prop(x['metric'], metric_props)['fmt']), axis=1)
        df['growth'] = df.apply(lambda x: self.helper.get_formatted_num(x['growth'], self.helper.get_metric_prop(x['metric'], metric_props)['growth_fmt']), axis=1)
        if self.impact_df_col in df.columns:
            df = df.rename(columns={self.impact_df_col: self.impact_col})
            df[self.impact_col] = df.apply(lambda x: self.helper.get_formatted_num(x[self.impact_col], self.impact_format), axis=1)

        if "impact_formula" in df.columns:
            df = df.drop("impact_formula", axis=1)

        df['metric'] = df['metric'].apply(lambda x: self.helper.get_metric_prop(x, metric_props).get("label", x))
        if 'parent_metric' in df.columns:
            df['parent_metric'] = df['parent_metric'].apply(lambda x: self.helper.get_metric_prop(x, metric_props).get("label", x) if x and x == x else x)

        return df

    def add_impacts_in_df(self, metric_df, driver_impact_formulas):
        try:
            if not driver_impact_formulas:
                return metric_df
            else:
                impacts = self.ic.calculate_impacts(metric_df, driver_impact_formulas)
                if impacts:
                    metric_df[self.impact_df_col] = metric_df.index.map(lambda x: impacts[x] if x in impacts else np.nan)
        except Exception as e:
            print(f"Error in calculating impacts: {e}")
        return metric_df

    def run(self, table, metrics, period_filters, query_filters=[], table_specific_filters={}, driver_metrics=[], view="", include_sparklines=True, two_year_filter=None, period_col_granularity='day', metric_props={}, add_impacts=False, impact_formulas={}):
        available_metrics = list(metric_props.keys())
        self._metric_props = metric_props

        if not metrics:
            raise exit_with_status(f"Ask user to provide at least one metric. Please do not make choice on user's behalf. Some examples of metrics are: {available_metrics}.")
        # set target metric to first metric
        self.target_metric = metrics[0]
        self.target_metric_label = self.helper.get_metric_prop(self.target_metric, metric_props).get("label", self.target_metric)
        self.impact_col = f"Impact on {self.target_metric_label}"
        target_metric_props = self.helper.get_metric_prop(self.target_metric, metric_props)
        if target_metric_props.get("hide_percentage_change"):
            self.impact_format = target_metric_props.get("growth_fmt")
        else:
            self.impact_format = target_metric_props.get("fmt")

        if self.target_metric not in metric_props:
            raise exit_with_status(f"Ask user to specify a valid metric. Please do not make choice on user's behalf. Please ask user to chose from {available_metrics}.")

        if add_impacts:
            driver_impact_formulas = impact_formulas.get(self.target_metric, {})
            impact_metrics = self.ic.get_component_metrics(driver_impact_formulas)
            additional_metrics = [self.helper.get_metric_prop(m, metric_props) for m in list(set(impact_metrics) - set(metrics))]
        else:
            additional_metrics = []
            driver_impact_formulas = {}

        metrics = [self.helper.get_metric_prop(m, metric_props) for m in metrics]

        # metric table
        metric_df = self._get_metric_growth(
            table = table,
            metrics = metrics+additional_metrics,
            period_filters = period_filters,
            query_filters = query_filters,
            table_specific_filters = table_specific_filters,
            view = view
        )

        metric_df = self.add_impacts_in_df(metric_df, driver_impact_formulas)
        metric_df = metric_df.loc[[m.get('name') for m in metrics if m.get('name') and m.get('name') in metric_df.index]]

        # add sparklines
        if include_sparklines:
            metric_df = self._add_sparklines(
                metric_df = metric_df,
                table = table,
                metrics = metrics,
                period_filters = period_filters,
                query_filters = query_filters,
                table_specific_filters = table_specific_filters,
                period_col_granularity = period_col_granularity,
                two_year_filter = two_year_filter,
                view = view
            )

        # add metric tree
        if driver_metrics:
            metric_df = self.combine_metric_tree(metric_df, self.target_metric, driver_metrics)

        self._metric_df = metric_df

        return metric_df
