import copy
from collections import defaultdict

import pandas as pd
from ar_analytics.trend import AdvanceTrend, GROWTH, DELTA
from ar_analytics.helpers.utils import Connector, is_using_max_sql_gen, exit_with_status, is_filter_token
from overproof_utilities import MenuColNames, OverproofSharedFn

class OverproofDataProvider(AdvanceTrend):
    def __init__(self, table: str, sql_exec: Connector, time: dict, dim_hierarchy: dict = {}, constrained_values={}, max_num_charts=10, df_provider=None):
        super().__init__(table, sql_exec, time, dim_hierarchy, constrained_values, max_num_charts, df_provider)
        self.helper = OverproofSharedFn()


    def check_count_metric(self, metric: dict) -> bool:
        met_name = metric.get('name')
        count_metrics = [MenuColNames.MENU_PLACEMENTS_METRIC.value, MenuColNames.VENUE_PLACEMENTS_METRIC.value]
        return met_name in count_metrics

    def calculate_market_share_denominator(
            self,
            metrics,
            breakouts=[],
            filters=[],
            order_cols=None,
            query_row_limit=None,
            subject_breakout=None
    ) -> pd.DataFrame:
        '''
        Calculate the denominator for the market share calculation.
        Provides the normal denominator for non-count metrics.
        Provides the sum of count metrics for the subject breakout as the denominator for count metrics.
        '''

        if subject_breakout:
            non_count_metrics = [m for m in metrics if not self.check_count_metric(m)]
            count_metrics = [m for m in metrics if self.check_count_metric(m)]
        else:
            non_count_metrics = metrics
            count_metrics = []

        non_count_df = pd.DataFrame()
        count_df = pd.DataFrame()

        if non_count_metrics:
            non_count_df = self.pull_data_func(non_count_metrics, breakouts, filters, order_cols, query_row_limit)

        if count_metrics:
            # groupby dims + subject_breakout, then sum over everything except the subject_breakout
            count_df = self.pull_data_func(count_metrics, breakouts + [subject_breakout], filters, order_cols,
                                           query_row_limit)
            if breakouts:
                count_df = count_df.groupby(breakouts).sum().reset_index()
            else:
                count_df = count_df.groupby(lambda x: True).sum().reset_index(drop=True)

        if not non_count_df.empty and not count_df.empty:
            df = pd.merge(non_count_df, count_df, on=breakouts, how='inner')
        elif non_count_df.empty and not count_df.empty:
            df = count_df
        elif not non_count_df.empty and count_df.empty:
            df = non_count_df
        else:
            df = pd.DataFrame()

        return df

    # Overwriting so that sales_uplift is considered a calculated metric
    # This will make it so pull_data is called to recalculate the total for sales uplift
    def get_metric_sql(self, metric):
        calculated_metrics, non_calculated_metrics = None, None
        if metric.get("sql") and metric.get("col") or metric.get("name") == MenuColNames.SALES_UPLIFT_METRIC.value:
            calculated_metrics = metric
        elif metric.get("col"):
            non_calculated_metrics = metric["name"]
        return calculated_metrics, non_calculated_metrics

    def _run_share(self, base_df, metrics, dims, fils, period_filter, table_specific_filters, top_n, top_n_direction, required_dim_vals):
        filters = copy.deepcopy(fils)
        base_df = base_df.copy()

        # create a dict of share metric properties
        underlying_metric_props = {}
        for metric in metrics:
            metric_dict = self.helper.get_metric_prop(metric, self.metric_props)
            underlying_metric = metric_dict.get("component_metric")

            # check that share metric has underlying metric details. Required for share calculations
            if not underlying_metric:
                raise exit_with_status(f"Component metric for '{metric}' not specified in metric properties")

            underlying_metric_dict = self.helper.get_metric_prop(underlying_metric, self.metric_props)

            underlying_metric_props[metric] = underlying_metric_dict

        # metric columns to select from data

        # # set share flag
        # for m in metrics:
        #     underlying_metric_props[m]['is_share'] = True
        #
        share_metric_props = [underlying_metric_props[m] for m in metrics]

        if period_filter:
            filters.append(period_filter)

        additional_filters = []
        for dim in dims:
            additional_filters.extend(table_specific_filters.get(dim, table_specific_filters.get('default', [])))

        # get share base
        join_cols = ['date_column', self.date_alias, 'metric']
        if self.date_sort_col:
            join_cols.append(self.pandas_sort_col)

        # rename metrics from component metric column to component metric
        rename_dict = {underlying_metric_props[m]['col']:
                           underlying_metric_props[m]['name'] for m in metrics}

        if dims:
            dim_dfs = []

            for dim in dims:

                breakout_label = self.helper.get_dimension_prop(dim, self.dim_props).get("label", dim)

                dim_required_vals = defaultdict(list)
                base_dim_df = base_df[base_df['dim'] == dim]

                # check if any of the filters are in owner hierarchy, remove them from market_filters
                market_filters = [f for f in filters if f['col'] not in self.dim_hier.owner_cols]

                # check if filters are the same for numerator and denominator
                # if it's the same then calculate contribution to total
                if market_filters == filters:
                    groupby = []
                    dim_join_cols = join_cols
                    self.contributions.append(breakout_label)
                # only breakout the denominator if it is not an owner column
                elif dim in self.dim_hier.owner_cols:
                    groupby = []
                    dim_join_cols = join_cols
                    self.contributions.append(breakout_label)
                else:
                    groupby = [dim]
                    self.share_within.append(breakout_label)
                    dim_join_cols = join_cols + ['dim', 'dim_val']
                    # get the dim_vals needed for denominator
                    dim_vals = list(base_dim_df['dim_val'].unique())
                    # dim_required_vals[dim] = [d.lower() for d in dim_vals]

                dim_market_df = self.get_trend_data(share_metric_props, [], market_filters + additional_filters, top_n, top_n_direction, dim_required_vals, is_share=True, subject_breakout=dim)

                dim_market_df['metric'] = dim_market_df['metric'].apply(lambda x: rename_dict.get(x, x))
                dim_market_df = dim_market_df.rename(columns={'value': 'market_value'})

                # join the market_df with the base_df
                base_dim_df = pd.merge(base_dim_df, dim_market_df, on=dim_join_cols, how='inner')

                dim_dfs.append(base_dim_df)
            market_df = pd.concat(dim_dfs, ignore_index=True)
        else:
            # check if any of the filters are in owner hierarchy, remove them from market_filters
            market_filters = [f for f in filters if f['col'] not in self.dim_hier.owner_cols]
            total_market_df = self.get_trend_data(share_metric_props, [], market_filters + additional_filters, top_n, top_n_direction, required_dim_vals, is_share=True)

            total_market_df['metric'] = total_market_df['metric'].apply(lambda x: rename_dict.get(x, x))
            # calculate market share
            total_market_df = total_market_df.rename(columns={'value': 'market_value'})

            market_df = pd.merge(base_df, total_market_df, on=join_cols, how='inner')

        # calculate market share
        market_df['market_share'] = market_df['value'] / market_df['market_value']
        dim_cols = ['dim_val', 'dim'] if dims else []
        market_df = market_df[[*join_cols, 'market_share'] + dim_cols]
        market_df = market_df.rename(columns={'market_share': 'value'})

        # rename metrics from component metric to share metric
        rename_dict = {underlying_metric_props[m]['name']: m for m in metrics}
        market_df['metric'] = market_df['metric'].apply(lambda x: rename_dict.get(x, x))

        return market_df


    def get_trend_data(self, metrics, dims, filters, top_n, top_n_direction, required_dim_vals, is_share=False, subject_breakout=None):
        use_max_sql_gen = is_using_max_sql_gen()

        referenced_table, sql = self.get_referenced_table_and_starting_sql(self.table, self.view)

        # process dim filters
        for f in filters:
            for dim in dims:
                if f['col'] == dim and f['op'].lower() in ['=', 'in']:
                    # make sure all dim filters are also required dim vals
                    if isinstance(f['val'], list):
                        required_dim_vals[dim].extend(f['val'])
                    else:
                        required_dim_vals[dim].append(f['val'])
                    # remove dim ambiguity
                    f['col'] = f"{referenced_table}.{dim}" if not use_max_sql_gen else dim
                    break

        # format metric sql
        calculated_metrics = []
        non_calculated_metrics = []

        if self.metric_name_column:
            c_metrics, nc_metrics = self.get_metric_sql(self.value_metric)
            if nc_metrics:
                non_calculated_metrics.append(nc_metrics)
            else:
                calculated_metrics.append(c_metrics)
            dims.append(self.metric_name_column)
        else:
            for metric in metrics:
                c_metrics, nc_metrics = self.get_metric_sql(metric)
                if nc_metrics:
                    non_calculated_metrics.append(nc_metrics)
                else:
                    calculated_metrics.append(c_metrics)

        if dims:
            # Get the data for the top 10 dim values (+ required dim values) by the first metric for each dimension
            dim_dfs = []

            for dim in dims:
                top_dim_vals = []
                if top_n:
                    first_metric = metrics[0]

                    top_dim_df = self.pull_data_func(metrics=[first_metric],
                                                     filters=filters,
                                                     breakouts=[dim],
                                                     order_cols=[{"col": first_metric["name"], "direction": top_n_direction}],
                                                     query_row_limit=top_n)

                    top_dim_vals = list(top_dim_df[dim].unique())

                if required_dim_vals.get(dim):
                    top_dim_vals = [v.lower() for v in top_dim_vals + required_dim_vals[dim]]
                    top_dim_vals = list(dict.fromkeys(top_dim_vals))
                else:
                    top_dim_vals = top_dim_vals

                if top_dim_vals:
                    datapull_filters = filters + [{"col": dim, "op": "IN", "val": top_dim_vals}]
                else:
                    datapull_filters = filters

                df = self.pull_data_func(metrics=metrics,
                                         filters=datapull_filters,
                                         breakouts=[dim] + [f"max_time_{self.time_granularity}"],
                                         order_cols=[{"col": f"max_time_{self.time_granularity}", "alias": "date_column", "direction": "ASC"}],
                                         query_row_limit=self.row_limit)

                    # df = self.calculate_market_share_denominator(
                    #     metrics=metrics,
                    #     breakouts=[f"max_time_{self.time_granularity}"],
                    #     filters=datapull_filters,
                    #     order_cols=[{"col": f"max_time_{self.time_granularity}", "alias": "date_column", "direction": "ASC"}],
                    #     query_row_limit=self.row_limit,
                    #     subject_breakout=dim
                    # )

                df.rename(columns={f"max_time_{self.time_granularity}": self.time_granularity}, inplace=True)

                self.check_row_limit(df)

                # calculate totals
                if not self.hide_totals:
                    totals_df = self.calculate_totals_df(df, calculated_metrics=calculated_metrics, non_calculated_metrics=non_calculated_metrics, filters=filters, dim=dim)
                    df = pd.concat([df, totals_df], axis=0)

                # rename dim values to 'dim_val', create dim column
                df['dim'] = dim
                df.rename(columns={dim: 'dim_val'}, inplace=True)

                dim_dfs.append(df)

            df = pd.concat(dim_dfs, axis=0)

        else:
            if not is_share:
                df = self.pull_data_func(metrics=metrics,
                                         filters=filters,
                                         breakouts=[f"max_time_{self.time_granularity}"],
                                         order_cols=[{"col": f"max_time_{self.time_granularity}", "alias": "date_column", "direction": "ASC"}],
                                         query_row_limit=self.row_limit)
            else:
                df = self.calculate_market_share_denominator(
                    metrics=metrics,
                    breakouts=[f"max_time_{self.time_granularity}"],
                    filters=filters,
                    order_cols=[{"col": f"max_time_{self.time_granularity}", "alias": "date_column", "direction": "ASC"}],
                    query_row_limit=self.row_limit,
                    subject_breakout=subject_breakout
                )
            df.rename(columns={f"max_time_{self.time_granularity}": self.time_granularity}, inplace=True)

            if 'date_column' not in df.columns:
                df['date_column'] = df[self.time_granularity]

            self.check_row_limit(df)

            # calculate totals
            if not self.hide_totals:
                totals_df = self.calculate_totals_df(df, calculated_metrics=calculated_metrics, non_calculated_metrics=non_calculated_metrics, filters=filters)
                df = pd.concat([df, totals_df], axis=0)

        if dims:
            id_vars = ['date_column', self.date_alias, 'dim_val', 'dim']
            df['dim'] = df['dim'].astype(str)
        else:
            id_vars = ['date_column', self.date_alias]

        if self.date_sort_col:
            id_vars.append(self.pandas_sort_col)

        metric_cols = [metric["name"] for metric in metrics]
        if not self.metric_name_column:
            df = df.melt(id_vars=id_vars, value_vars=metric_cols, var_name='metric', value_name='value')
        else:
            df = df.rename(columns={self.metric_name_column: 'metric', self.value_metric["col"]: 'value'})

        df['value'] = df['value'].astype(float)

        # sql query forces lowercase cols, revert back to original case
        metric_map = {metric.lower(): metric for metric in metric_cols}
        df['metric'] = df['metric'].apply(lambda x: metric_map.get(x, x))

        print(df.head().to_string())

        if not self.date_sort_col:
            df["date_column"] = pd.to_datetime(df["date_column"])

        if len(df) > 0:
            self.actual_first_period, self.actual_last_period = df[self.date_alias].iloc[0], df[self.date_alias].iloc[-1]
        else:
            self.actual_first_period, self.actual_last_period = "", ""

        self.show_labels = len(df["date_column"].unique()) < 25

        return df
