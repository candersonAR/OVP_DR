import pandas as pd
import numpy as np
import time

from ar_analytics.helpers.utils import get_viz_header, old_get_filters_headline, exit_with_status
from overproof_utilities import OverproofSharedFn, calculate_market_share_denominator
from ar_analytics.market_share_breakdown import MarketShareBreakdown

class OverproofDataProvider(MarketShareBreakdown):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = OverproofSharedFn()

    def process_subject_filter(self, query_filters):

        # get subject dim and member
        subject_filter = self.dim_hierarchy.get_lowest_level_ms_dim_filter(query_filters)
        subject_dim = subject_filter['col'] if subject_filter else None
        subject_member = subject_filter['val'] if subject_filter else None

        # If there are multiple potential subject dims, keep the lowest and drop the rest
        potential_subject_dims = list(
            set([f['col'] for f in query_filters if f['col'] in self.dim_hierarchy.owner_cols]))
        if len(potential_subject_dims) > 1:
            query_filters = [f for f in query_filters if f['col'] not in potential_subject_dims]

        if not subject_member:
            exit_with_status("Ask user to provide a subject filter to calculate market share.")

        # if there are more than 1 filter for the subject dim, drop the rest
        subject_filters = [f for f in query_filters if f['col'] == subject_dim]
        query_filters = [f for f in query_filters if f['col'] != subject_dim]
        if len(subject_filters) > 1:
            subject_dim_label = self.dim_props.get(subject_dim, {}).get('label', subject_dim)
            self.notes.append(
                f"Analysis focuses on the subject {subject_dim_label} '{subject_member}' only. You have been provided only limited facts. the user has a more complete table presented to them. Only respond using facts presented in the data above, let the user know more data might be presented on the table or chart on the screen.")

        query_filters.append(subject_filter)

        subject_member = subject_member.lower()

        return subject_dim, subject_member, subject_filter, query_filters

    def get_drivers_df(self, table, breakout, driver_metrics, query_filters, dim_member_filters, share_type='share',
                       parent_breakout=None, subject_dim=None):

        driver_cols = [m['name'] for m in driver_metrics]
        market_rename_dict = {breakout: 'dim_member'}
        drivers_rename_dict = {breakout: 'dim_member'}
        for metric in driver_metrics:
            market_rename_dict[metric['name']] = metric['name'] + '_market_size'
            drivers_rename_dict[metric['name']] = metric['name']

        market_filters = [f for f in query_filters if f['col'] != self.subject_dim]

        # if breakout is subject_dim, then get market sizes for each metric without breakout
        if breakout == self.subject_dim:
            # set class variable for subject market size data for contribution

            #428507 vs 86197
            self.df_market_curr = calculate_market_share_denominator(
                pull_data_func = self.pull_data_func,
                metrics=driver_metrics,
                filters=market_filters + [self.curr_period],
                subject_breakout=breakout
            )
            self.check_row_limit(self.df_market_curr)

            self.df_market_curr[driver_cols] = self.df_market_curr[driver_cols].astype(float)
            self.df_market_curr.rename(columns=market_rename_dict, inplace=True)

            self.df_market_comp = calculate_market_share_denominator(
                pull_data_func = self.pull_data_func,
                metrics=driver_metrics,
                filters=market_filters + [self.comp_period],
                subject_breakout=breakout
            )
            self.check_row_limit(self.df_market_comp)

            self.df_market_comp[driver_cols] = self.df_market_comp[driver_cols].astype(float)
            self.df_market_comp.rename(columns=market_rename_dict, inplace=True)

        else:
            # get current market size data
            # self.df_market_curr = self.pull_data_func(metrics=driver_metrics, breakouts=[breakout],
            #                            filters=market_filters + [self.curr_period])

            self.df_market_curr = calculate_market_share_denominator(
                pull_data_func = self.pull_data_func,
                metrics=driver_metrics,
                filters=market_filters + [self.curr_period],
                breakouts=[breakout],
                subject_breakout=subject_dim
            )
            self.check_row_limit(self.df_market_curr)

            self.df_market_curr[driver_cols] = self.df_market_curr[driver_cols].astype(float)
            self.df_market_curr.rename(columns=market_rename_dict, inplace=True)

            # get comp market size data
            self.df_market_comp = calculate_market_share_denominator(
                pull_data_func = self.pull_data_func,
                metrics=driver_metrics,
                filters=market_filters + [self.comp_period],
                breakouts=[breakout],
                subject_breakout=subject_dim
            )

            self.check_row_limit(self.df_market_comp)

            self.df_market_comp[driver_cols] = self.df_market_comp[driver_cols].astype(float)
            self.df_market_comp.rename(columns=market_rename_dict, inplace=True)

        query_breakouts = [breakout]
        if parent_breakout:
            query_breakouts.append(parent_breakout)

        # get current driver data
        df_drivers_curr = self.pull_data_func(metrics=driver_metrics,
                                    filters=query_filters + dim_member_filters + [self.curr_period],
                                    breakouts=query_breakouts)
        self.check_row_limit(df_drivers_curr)

        df_drivers_curr[driver_cols] = df_drivers_curr[driver_cols].astype(float)
        df_drivers_curr.rename(columns=drivers_rename_dict, inplace=True)
        # merge in market size and calculate share
        if breakout == self.subject_dim or share_type in ['contribution']:
            for metric in driver_metrics:
                df_drivers_curr[metric['name'] + '_market_size'] = \
                self.df_market_curr[metric['name'] + '_market_size'].values[0]
        else:
            df_drivers_curr = pd.merge(df_drivers_curr, self.df_market_curr, on='dim_member', how='inner')

        for metric in driver_metrics:
            df_drivers_curr[metric['name'] + '_share'] = df_drivers_curr[metric['name']].div(
                df_drivers_curr[metric['name'] + '_market_size'], fill_value=0)

        # get comp driver data
        df_drivers_comp = self.pull_data_func(metrics=driver_metrics,
                                    filters=query_filters + dim_member_filters + [self.comp_period],
                                    breakouts=query_breakouts)
        self.check_row_limit(df_drivers_comp)

        df_drivers_comp[driver_cols] = df_drivers_comp[driver_cols].astype(float)
        df_drivers_comp.rename(columns=drivers_rename_dict, inplace=True)
        # merge in market size and calculate share
        if breakout == self.subject_dim or share_type in ['contribution']:
            for metric in driver_metrics:
                df_drivers_comp[metric['name'] + '_market_size'] = \
                self.df_market_comp[metric['name'] + '_market_size'].values[0]
        else:
            df_drivers_comp = pd.merge(df_drivers_comp, self.df_market_comp, on='dim_member', how='outer')
        for metric in driver_metrics:
            df_drivers_comp[metric['name'] + '_share'] = df_drivers_comp[metric['name']].div(
                df_drivers_comp[metric['name'] + '_market_size'], fill_value=0)

        join_dims = ['dim_member']
        if parent_breakout:
            join_dims.append(parent_breakout)

        df_drivers = pd.merge(df_drivers_curr, df_drivers_comp, on=join_dims, how='inner', suffixes=('_curr', '_comp'))
        # df_drivers = pd.merge(df_drivers_curr, df_drivers_comp, on=join_dims, how='outer', suffixes=('_curr', '_comp'))
        df_drivers = df_drivers.fillna(0)
        for metric in driver_metrics:
            df_drivers[metric['name'] + '_share_change'] = df_drivers[metric['name'] + '_share_curr'] - df_drivers[
                metric['name'] + '_share_comp']
            df_drivers[metric['name'] + '_diff'] = df_drivers[metric['name'] + '_curr'] - df_drivers[
                metric['name'] + '_comp']
            df_drivers[metric['name'] + '_diff_pct'] = df_drivers[metric['name'] + '_diff'].div(
                np.abs(df_drivers[metric['name'] + '_comp']), fill_value=0)

        return df_drivers

    def transform_subject_df(self, subject_df, subject_dim, top_n, market_filters):

        # get subject market size for each period
        if self.is_agg_metrics:
            self.subject_market_df = subject_df.groupby(self.period_col)['metric'].sum().reset_index()
            self.subject_market_df.rename(columns={'metric': 'market_size'}, inplace=True)
        else:
            print("Check 12")
            self.subject_market_df = self.pull_data_func(metrics=[self.metric], filters=market_filters + [self.trend_period],
                               breakouts=[self.period_col])
            self.check_row_limit(self.subject_market_df)

            self.subject_market_df.rename(columns={self.metric['name']: 'market_size'}, inplace=True)
            self.subject_market_df['market_size'] = self.subject_market_df['market_size'].astype(float)
            

        # filter to current period to get top n members of subject dim
        curr_df = subject_df[
            (subject_df[self.period_col] >= self.curr_start_date) & (subject_df[self.period_col] <= self.curr_end_date)]
        if curr_df.empty:
            exit_with_status("No data available for the current period. Ask user to try a different time range.")
        if top_n:
            top_members = \
            curr_df.groupby(subject_dim)['metric'].sum().reset_index().sort_values(by='metric', ascending=False).head(
                top_n)[subject_dim].str.lower().tolist()
        else:
            top_members = curr_df[subject_dim].str.lower().tolist()
        top_members.append(self.subject_member)

        # filter to top members
        subject_df = subject_df[subject_df[subject_dim].str.lower().isin(top_members)]

        # make sure subject is available for all periods
        subject_df = self.get_data_for_all_periods(subject_df, dim=subject_dim)

        # merge in market size
        subject_df = pd.merge(subject_df, self.subject_market_df, on=self.period_col, how='inner')

        # process share df
        df = self.process_share_df(subject_df, subject_dim)

        return df

    def transform_breakout_df(self, breakout_df, breakout_dim, market_filters, top_n=None):

        # filter to subject dim member
        breakouts_subject_df = breakout_df[breakout_df[self.subject_dim].str.lower() == self.subject_member]

        # filter to top n members of breakout
        if top_n:
            # filter to current period
            curr_df = breakouts_subject_df[(breakouts_subject_df[self.period_col] >= self.curr_start_date) & (
                        breakouts_subject_df[self.period_col] <= self.curr_end_date)]
            top_members = \
            curr_df.groupby(breakout_dim)['metric'].sum().reset_index().sort_values(by='metric', ascending=False).head(
                top_n)[breakout_dim].str.lower().tolist()
            breakouts_subject_df = breakouts_subject_df[
                breakouts_subject_df[breakout_dim].str.lower().isin(top_members)]

        breakouts_subject_df = breakouts_subject_df.groupby([self.period_col, breakout_dim])[
            'metric'].sum().reset_index()

        # df for market size by breakout dim_member
        if self.is_agg_metrics:
            breakout_market_df = breakout_df.groupby([self.period_col, breakout_dim])['metric'].sum().reset_index()
            breakout_market_df.rename(columns={'metric': 'market_size'}, inplace=True)
        else:
            print("Check 13")
            breakout_market_df = self.pull_data_func(metrics=[self.metric], filters=market_filters + [self.trend_period],
                               breakouts=[self.period_col, breakout_dim])
            self.check_row_limit(breakout_market_df)
            breakout_market_df.rename(columns={self.metric['name']: 'market_size'}, inplace=True)
            breakout_market_df['market_size'] = breakout_market_df['market_size'].astype(float)

        # make sure breakout dim is available for all periods
        breakouts_subject_df = self.get_data_for_all_periods(breakouts_subject_df, dim=breakout_dim)

        # merge in market size
        merged_df = pd.merge(breakouts_subject_df, breakout_market_df, on=[self.period_col, breakout_dim], how='inner')

        # process share df
        df = self.process_share_df(merged_df, breakout_dim)

        return df

    def get_display_tables(self, viz_func=None):
        tables = {}
        for tab_name, df in self.display_dfs.items():
            for col in ['dim_member', 'parent_dim_member', 'msg', 'trend_msg']:
                if col in df.columns:
                    # removing html brackets from dim_member and parent_dim_member here instead of in click_html
                    # because the click_html might have valid html, e.g. click on image run trend
                    df[col] = df[col].apply(lambda x: self.remove_html_brackets(x))

                cols_to_keep = ['parent_dim_member', 'dim_member', 'share_curr', 'share_comp', 'share_change',
                                'share_change_mat', 'sparkline', 'is_subject', 'msg']
                if 'is_collapsible' in df.columns:
                    cols_to_keep.append('is_collapsible')
                col_rename_dict = {}
                col_rename_dict['dim_member'] = f"Share by {tab_name}"

            if self.date_labels.get('start_date') == self.date_labels.get('end_date'):
                col_rename_dict['share_curr'] = str(self.date_labels.get('start_date'))
            else:
                col_rename_dict[
                    'share_curr'] = f"{str(self.date_labels.get('start_date'))} to {str(self.date_labels.get('end_date'))}"

            if self.date_labels.get('compare_start_date') == self.date_labels.get('compare_end_date'):
                col_rename_dict['share_comp'] = str(self.date_labels.get('compare_start_date'))
            else:
                col_rename_dict[
                    'share_comp'] = f"{str(self.date_labels.get('compare_start_date'))} to {str(self.date_labels.get('compare_end_date'))}"

            col_rename_dict["share_change"] = f"Share Change {self.env.growth_type}"
            col_rename_dict["share_change_mat"] = f"L12M Chg Y/Y"

            df['dim_member'] = df['dim_member'].apply(lambda x: self.replace_special_chars(x))
            if 'parent_dim_member' in df.columns:
                if df['parent_dim_member'].isnull().all():
                    cols_to_keep.remove('parent_dim_member')
                else:
                    df['parent_dim_member'] = df['parent_dim_member'].apply(lambda x: self.replace_special_chars(x))
            if 'level' in df.columns:
                df['dim_member'] = df.apply(
                    lambda row: f"{' ' * 3 * int(row['level'])}-{row['dim_member']}" if row['level'] > 0 else row[
                        'dim_member'], axis=1)
                df["dim_member"] = df["dim_member"].apply(lambda x: x.replace("_", " "))

            if self.include_drivers:
                if 'subject_df' in df.columns:
                    for section in self.subject_metric_drivers:
                        for driver in self.subject_metric_drivers[section]:
                            cols_to_keep.append(driver)
                            col_rename_dict[driver] = self.metric_drivers_labels[driver]
                else:
                    for section in self.decomposition_metric_drivers:
                        for driver in self.decomposition_metric_drivers[section]:
                            cols_to_keep.append(driver)
                            col_rename_dict[driver] = self.metric_drivers_labels[driver]

            df = df[[col for col in cols_to_keep if col in df.columns]]

            # rename columns for followup
            if "msg" in df.columns:
                col_rename_dict["msg"] = "followup_nl"

            df = df.rename(columns=col_rename_dict)

            tables[tab_name] = df

        return tables

    def adding_metric_columns(self, df, main_metric, dim, top_n):
        main_metric_col = main_metric["name"]
        for col in df.columns:
            if main_metric_col in col:
                if "market_size" in col or "_share_" in col:
                    new_col_name = col.replace(main_metric_col, "").lstrip("_")
                elif col == f"{main_metric_col}_diff" or col == f"{main_metric_col}_diff_pct":
                    new_col_name = col.replace(main_metric_col, "").lstrip("_")
                else:
                    new_col_name = col.replace(main_metric_col, "metric")
                df[new_col_name] = df[col]

        # add top n
        if dim == self.subject_dim:
            top_members = df.sort_values(by='metric_curr', ascending=False).head(top_n)['dim_member'].str.lower().tolist()
            top_members = top_members + [str(self.subject_member).lower()]
            df = df[df['dim_member'].str.lower().isin(top_members)]
        else:
            df = df.sort_values(by='metric_curr', ascending=False).head(top_n)

        # add share diff cols
        df["share_change"] = df["share_curr"] - df["share_comp"]
        df["share_change_mat"] = np.nan
        df["sparkline"] = np.nan
        df['dim'] = dim

        df = df.sort_values(by='metric_curr', ascending=False, na_position='last')

        df['is_subject'] = False
        if dim == self.subject_dim:
            df['is_subject'] = df['dim_member'].apply(lambda x: x.lower() == self.subject_member)

        # add rank column
        df["rank_curr"] = df["metric_curr"].rank(ascending=False, method='dense')
        df["rank_comp"] = df["metric_comp"].rank(ascending=False, method='dense')
        df["rank_change"] = df["rank_curr"] - df["rank_comp"]

        if dim == self.subject_dim and f"{main_metric_col}_share_change" not in df.columns:
            df[f"{main_metric_col}_share_change"] = df[f"{main_metric_col}_share_curr"] - df[f"{main_metric_col}_share_comp"]

        return df

    def run(self, table, metric, period_filters, default_date_granularity, top_n=10, query_filters=[], breakouts=[],
            view="", metric_props={}, dim_props={}, include_drivers=False, date_labels={}, growth_type="",
            periods_in_year={}, impact_calcs={}, subject_metric_config={}, decomposition_display_config={}):

        self.metric, self.share_metric = self.get_share_and_component_metric(metric, metric_props)

        if self.share_metric not in metric_props.values():
            exit_with_status(
                f"Please inform user that the share metric {self.share_metric} not found in the dataset. Please choose a different metric.")

        self.dim_props = dim_props
        self.metric_props = metric_props
        self.periods_in_year = periods_in_year
        self.date_labels = date_labels
        self.default_date_granularity = default_date_granularity
        self.all_share_metrics = [met for met, props in metric_props.items() if
                                  props.get("metric_type") == "share" or props.get("is_share")]

        if isinstance(top_n, str):
            top_n = int(top_n)
        if top_n == 1:
            top_n = 10

        self.view = view

        # if not config found for subject_metric_config or decomposition_display_config, then don't include drivers
        if include_drivers and (subject_metric_config or decomposition_display_config):
            self.include_drivers = include_drivers
        else:
            self.include_drivers = False

        self.set_metric_driver_html_sections(subject_metric_config, decomposition_display_config)

        decomp_metrics_names, impact_metric_names, token_metrics = self.get_driver_metrics(decomposition_display_config)

        # get all metrics needed for the query
        query_metrics = self.get_metrics_for_query(subject_metric_config, impact_calcs, impact_metric_names,
                                                   decomp_metrics_names, metric_props)
        if set([m['name'] for m in query_metrics]) - set(list(self.metric_props.keys())):
            invalid_metrics = set([m['name'] for m in query_metrics]) - set(list(self.metric_props.keys()))
            exit_with_status(
                f"Invalid metrics {invalid_metrics} found in configuration. Ask user to reach out to admin to configure correct metrics from available metrics in dataset.")

        print(f"Query Metrics: {query_metrics}")

        # metric objects for impact and share impact metrics
        self.impact_metrics = [self.helper.get_metric_prop(m, metric_props) for m in impact_metric_names]
        self.share_impact_metrics = [m for m in self.impact_metrics if m.get('metric_type') == 'share']
        self.impact_metrics = [m for m in self.impact_metrics if m.get('metric_type') != 'share']

        self.share_metric_label = self.share_metric.get('label', self.share_metric['name'])

        self.subject_dim, self.subject_member, self.subject_filter, query_filters = self.process_subject_filter(query_filters)

        self.core_fact_cols = [
            'dim',
            'dim_member',
            'is_subject',
            'share_curr',
            'share_comp',
            'share_change',
            'share_change_mat',
        ]

        self.facts_rename_dict = self.get_rename_dict(query_metrics, self.share_metric_label)

        print("period_filters", period_filters)
        self.process_period_filters(period_filters)

        breakouts = self.process_breakouts(breakouts, query_filters)

        # if any invalid breakouts, exit with status
        if set([b.get('dim') for b in breakouts]) - set(dim_props.keys()):
            invalid_breakouts = set([b.get('dim') for b in breakouts]) - set(dim_props.keys())
            exit_with_status(
                f"Invalid breakouts {invalid_breakouts} found in configuration. Ask user to reach out to admin to configure correct dimension from available dimension in dataset.")

        print(f"\nBreakouts:\n{breakouts}")

        market_filters = [f for f in query_filters if f['col'] != self.subject_dim]

        dim_filter_str = self.get_drilldown_message_suffix(market_filters, dim_props)

        self.subject_dim_label = dim_props.get(self.subject_dim, {}).get('label', self.subject_dim)
        # self.notes.append(f"Analysis limited to the top {top_n} {self.subject_dim_label}s")

        dfs = {}
        start_time = time.time()

        self.is_agg_metrics = True

        # get subject df
        self.dimensions_analyzed.append(self.subject_dim)

        subject_df = self.get_drivers_df(table, self.subject_dim, [self.metric], market_filters, [])
        subject_df = self.adding_metric_columns(df=subject_df, main_metric=self.metric, dim=self.subject_dim, top_n=top_n)
        self.check_row_limit(subject_df)

        if subject_df.empty:
            exit_with_status(
                f"No data found for {self.subject_dim_label} {self.subject_member}{dim_filter_str}. Ask user to try a different set of filters.")


        subject_df['level'] = 0
        subject_df['parent_dim'] = None
        subject_df['parent_dim_member'] = None
        subject_df['msg'] = subject_df.apply(lambda
                                                 x: f"Run the same analysis on {self.subject_dim_label} {x['dim_member']}{dim_filter_str} for same time period." if not
        x['is_subject'] else "", axis=1)
        subject_df['trend_msg'] = subject_df.apply(
            lambda x: f"Run {self.share_metric_label} trend for {self.subject_dim_label} {x['dim_member']}{dim_filter_str}",
            axis=1)
        subject_df['is_collapsible'] = False

        # get drivers metrics
        # todo: include drivers turn off
        # if self.include_drivers:
        #     dim_member_filters = self.get_dim_member_filters(subject_df, self.subject_dim)
        #     drivers_df = self.get_drivers_df(table, self.subject_dim, query_metrics, market_filters, dim_member_filters)
        #     subject_df = pd.merge(subject_df, drivers_df, on='dim_member', how='left')

        # save subject row
        self.subject_row = subject_df[subject_df['is_subject']].copy()

        if self.include_drivers:
            if 'fair_share' in token_metrics:
                self.apply_fair_share(self.subject_row)
            self.apply_share_impact_calcs(self.subject_row, self.share_impact_metrics)
            self.apply_calc_impacts(self.subject_row, self.impact_metrics, impact_calcs)

        # mark df as subject_df
        subject_df['subject_df'] = True

        dfs[self.subject_dim_label] = subject_df
        for breakout in breakouts:
            breakout_dim = breakout['dim']
            self.dimensions_analyzed.append(breakout_dim)
            breakout_dim_label = dim_props.get(breakout_dim, {}).get('label', breakout_dim)
            breakout_label = breakout.get("tab_label", breakout_dim_label)
            share_type = breakout.get("type")  # share or contribution

            if share_type == 'share':
                breakout_filters = market_filters + [self.trend_period]
                if self.is_agg_metrics:
                    breakout_filters.append(self.subject_filter)

                df = self.get_drivers_df(table, breakout_dim, [self.metric], query_filters,
                                                     [])
                df = self.adding_metric_columns(df=df, main_metric=self.metric, dim=breakout_dim, top_n=top_n)


                # todo: turn include_drivers off
                # if self.include_drivers:
                #     drivers_df = self.get_drivers_df(table, breakout_dim, query_metrics, query_filters,
                #                                      dim_member_filters)
                #     df = pd.merge(df, drivers_df, on='dim_member', how='left')

                df['level'] = breakout['level']
                df['parent_dim'] = None
                df['parent_dim_member'] = None

                # add drilldown message
                df['msg'] = df.apply(lambda
                                         x: f"Run the same analysis on {x['dim']} {x['dim_member']} for {self.subject_dim_label} {self.subject_member}{dim_filter_str} for same time period.",
                                     axis=1)
                df['trend_msg'] = df.apply(lambda
                                               x: f"Run {self.share_metric_label} trend for {x['dim']} {x['dim_member']} for {self.subject_dim_label} {self.subject_member}{dim_filter_str}",
                                           axis=1)

                # make row non collapsable
                df['is_collapsible'] = False

            elif share_type == 'contribution':
                drilldown = breakout.get("drilldown")

                # pull data using query_filters
                df = self.get_drivers_df(table, breakout_dim, [self.metric], query_filters,
                                         [], subject_dim=self.subject_dim)
                df = self.adding_metric_columns(df=df, main_metric=self.metric, dim=breakout_dim, top_n=top_n)
                self.check_row_limit(df)

                dim_member_filters = self.get_dim_member_filters(df, breakout_dim)

                df['level'] = breakout['level']
                df['parent_dim'] = None
                df['parent_dim_member'] = None

                # add drilldown message
                df['msg'] = df.apply(lambda
                                         x: f"Run the same analysis for {breakout_dim_label} {x['dim_member']}{dim_filter_str} for same time period.",
                                     axis=1)
                df['trend_msg'] = df.apply(lambda
                                               x: f"Run {self.share_metric_label} trend for {breakout_dim_label} {x['dim_member']}{dim_filter_str}",
                                           axis=1)

                drilldown = False
                if drilldown:

                    # make parent row collapsable
                    df['is_collapsible'] = True

                    drilldown_dim = drilldown['dim']

                    # pull data for drilldown dim using query_filters + top dim_members of parent
                    self.dimensions_analyzed.append(drilldown_dim)

                    drilldown_df = self.pull_data_func(metrics=[self.metric],
                                             filters=query_filters + dim_member_filters + [self.trend_period],
                                             breakouts=[breakout_dim, drilldown_dim, self.period_col],
                                             order_cols=[{"col": self.period_col, "direction": "ASC"}])
                    self.check_row_limit(drilldown_df)

                    drilldown_df.rename(columns={self.metric['name']: 'metric'}, inplace=True)
                    drilldown_df['metric'] = drilldown_df['metric'].astype(float)

                    # get driver metrics for drilldown
                    dim_member_filters = self.get_dim_member_filters(drilldown_df, drilldown_dim, col=drilldown_dim)
                    if self.include_drivers:
                        drivers_df = self.get_drivers_df(table, drilldown_dim, query_metrics, query_filters,
                                                         dim_member_filters, share_type='contribution',
                                                         parent_breakout=breakout_dim)

                    # get drilldowns for each breakout dim member
                    breakout_dim_members = df['dim_member'].tolist()
                    for dim_member in breakout_dim_members:
                        if self.include_drivers:
                            drivers_df_filtered = drivers_df[drivers_df[breakout_dim] == dim_member].copy()
                            drivers_df_filtered.drop(columns=[breakout_dim], inplace=True)

                        drilldown_df_filtered = drilldown_df[drilldown_df[breakout_dim] == dim_member].copy()
                        drilldown_df_filtered.drop(columns=[breakout_dim], inplace=True)

                        # transform contribution df
                        drilldown_transformed_df = self.transform_contribution_df(drilldown_df_filtered, drilldown_dim,
                                                                                  top_n)
                        if self.include_drivers:
                            drilldown_transformed_df = pd.merge(drilldown_transformed_df, drivers_df_filtered,
                                                                on='dim_member', how='left')
                        drilldown_transformed_df['level'] = drilldown['level']
                        drilldown_transformed_df['parent_dim'] = breakout_dim
                        drilldown_transformed_df['parent_dim_member'] = dim_member

                        # add drilldown message
                        drilldown_dim_label = dim_props.get(drilldown_dim, {}).get('label', drilldown_dim)
                        drilldown_transformed_df['msg'] = drilldown_transformed_df.apply(lambda
                                                                                             x: f"Run the same analysis for {self.subject_dim_label} {self.subject_member}, {drilldown_dim_label} {x['dim_member']} in {breakout_dim_label} {dim_member}{dim_filter_str} for same time period.",
                                                                                         axis=1)
                        drilldown_transformed_df['trend_msg'] = drilldown_transformed_df.apply(lambda
                                                                                                   x: f"Run {self.share_metric_label} trend for {drilldown_dim_label} {x['dim_member']} in {breakout_dim_label} {dim_member}{dim_filter_str} for same time period.",
                                                                                               axis=1)

                        # make row non collapsable
                        drilldown_transformed_df['is_collapsible'] = False

                        # concat drilldown_transformed_df to df, by placing drilldown_transformed_df rows after the corresponding row of the parent dim_member
                        df = df.reset_index(drop=True)
                        idx = df.index[(df['dim_member'] == dim_member) & (df['dim'] == breakout_dim)].tolist()[0]
                        df = pd.concat([df.iloc[:idx + 1], drilldown_transformed_df, df.iloc[idx + 1:]]).reset_index(
                            drop=True)

            df['share_type'] = breakout['type']

            if self.include_drivers:
                if 'fair_share' in token_metrics:
                    self.apply_fair_share(df)
                self.apply_share_impact_calcs(df, self.share_impact_metrics)
                self.apply_calc_impacts(df, self.impact_metrics, impact_calcs)

            # concat subject row to the top for non-subject breakouts
            if isinstance(self.subject_row, pd.DataFrame):
                df = pd.concat([self.subject_row, df])

            if not df.empty:
                dfs[breakout_label] = df

        end_time = time.time()
        exec_time = end_time - start_time
        print(f"\nTotal Execution Time: {exec_time:.2f}s")

        # subject facts
        self.subject_facts = self.get_subject_facts(query_metrics)

        # peers facts
        self.top_peers_facts, self.bottom_peers_facts = self.get_peers_facts(subject_df, query_metrics)

        # market share subject facts
        self.market_share_subject_facts = self.get_market_share_subject_facts(subject_df, query_metrics)

        self.suggestions = []

        # breakout and driver facts rely on impacts
        self.top_breakouts_facts = pd.DataFrame()
        self.bottom_breakouts_facts = pd.DataFrame()
        self.metric_driver_challenges_facts = pd.DataFrame()
        if self.include_drivers:
            # breakout facts
            self.top_breakouts_facts, self.bottom_breakouts_facts, self.bottom_growth_breakouts = self.get_breakout_facts(
                dfs)
            # metric driver challenges facts
            self.metric_driver_challenges_facts = self.get_metric_driver_challenges_facts(dfs)

            # get suggestions based on bottom breakouts facts, use bottom growth if no negative impacts exist
            if self.bottom_breakouts_facts.empty:
                for row in self.bottom_growth_breakouts.itertuples():
                    if row.share_type == 'contribution':
                        if row.parent_dim and row.parent_dim_member:
                            self.suggestions.append({
                                                        "label": f"Analyze performance of {row.dim} {row.dim_member} in {row.parent_dim} {row.parent_dim_member}",
                                                        "question": f"Run the same analysis for {row.dim} {row.dim_member} in {row.parent_dim} {row.parent_dim_member}{dim_filter_str} same time period."})
                        else:
                            self.suggestions.append({"label": f"Analyze performance of {row.dim} {row.dim_member}",
                                                     "question": f"Run the same analysis for {row.dim} {row.dim_member}{dim_filter_str} same time period."})
                    else:
                        self.suggestions.append({"label": f"Analyze performance of {row.dim} {row.dim_member}",
                                                 "question": f"Run the same analysis on {row.dim} {row.dim_member} for {self.subject_dim_label} {self.subject_member}{dim_filter_str} same time period."})
            else:
                for row in self.bottom_breakouts_facts.itertuples():
                    if row.share_type == 'contribution':
                        if row.parent_dim and row.parent_dim_member:
                            self.suggestions.append({
                                                        "label": f"Analyze performance of {row.dim} {row.dim_member} in {row.parent_dim} {row.parent_dim_member}",
                                                        "question": f"Run the same analysis for {row.dim} {row.dim_member} in {row.parent_dim} {row.parent_dim_member}{dim_filter_str} same time period."})
                        else:
                            self.suggestions.append({"label": f"Analyze performance of {row.dim} {row.dim_member}",
                                                     "question": f"Run the same analysis for {row.dim} {row.dim_member}{dim_filter_str} same time period."})
                    else:
                        self.suggestions.append({"label": f"Analyze performance of {row.dim} {row.dim_member}",
                                                 "question": f"Run the same analysis on {row.dim} {row.dim_member} for {self.subject_dim_label} {self.subject_member}{dim_filter_str} same time period."})

        # format dfs
        for key, df in dfs.items():
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            df[numeric_cols] = df[numeric_cols].astype(object)
            df[numeric_cols] = df[numeric_cols].fillna("Null")
            dfs[key] = self.format_df(df, query_metrics)

        # remove columns not applicable to contribution tables
        for key, df in dfs.items():
            if 'share_type' in df.columns and len(df) > 1:
                # index 1 to avoid subject row
                if df['share_type'].values[1] == 'contribution':
                    if 'fair_share' in df.columns:
                        df.drop(columns=['fair_share'], inplace=True)

        # generate table dims for column headers
        for key, df in dfs.items():
            table_dims = df[df['is_subject'] == False]['dim'].unique().tolist()
            table_dims = [dim_props.get(d, {}).get('label', d) for d in table_dims]
            table_dims = ' | '.join(table_dims)
            dfs[key]['table_dims'] = table_dims

        self.subject_member_label = self.subject_row['dim_member'].values[0]

        # market are all the filter vals that arent the subject dim
        market = [f for f in query_filters if f['col'] != self.subject_dim]
        market_str = old_get_filters_headline(query_filters=market, headline_seperator=', ', metric_props=metric_props,
                                              dim_props=dim_props) or "Total"
        title = f"Share of {self.subject_member_label} within {market_str}"
        if date_labels['start_date'] == date_labels['end_date']:
            date_str = date_labels['start_date']
        else:
            date_str = f"{date_labels['start_date']} to {date_labels['end_date']}"
        subtitle = f"{self.share_metric_label} Analysis • {date_str} {growth_type}"
        self.warning_message = self.get_warning_messages()
        self.title = title
        self.subtitle = subtitle
        self.viz_header = get_viz_header(title=title, subtitle=subtitle, warning_messages=self.get_warning_messages())

        if self.compare_date_warning_msg:
            self.notes.append(self.compare_date_warning_msg)

        self.notes.append(self.get_analysis_message(self.share_metric, query_filters, date_labels))
        # add notes about dimensions analyzed
        dimensions_analyzed_str = self.helper.and_comma_join(
            [dim_props.get(d, {}).get('label', d) for d in self.dimensions_analyzed if d])
        self.notes.append(f"Analysis only includes following dimensions {dimensions_analyzed_str}.")

        messages = self.notes or ["Analysis was completed as requested."]
        self.df_notes = pd.DataFrame({"Note to the assistant:": messages})

        self.display_dfs = dfs
        self.default_table_template = self.get_default_table_jinja()

        return dfs

