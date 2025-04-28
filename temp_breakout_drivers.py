import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from ar_analytics.helpers.utils import Connector, DimensionHierarchy, pull_data, is_filter_token, \
    is_using_max_sql_gen, old_split_dim_and_metric_filters, SharedFn, exit_with_status, fmt_num, fmt_sign_int

from temp_util import sparkline


class BreakoutDrivers:
    def __init__(self, dim_hierarchy, dim_val_map={}, sql_exec:Connector=None, df_provider=None, sp=None):
        # dim_hierarchy
        self.dim_hier = DimensionHierarchy(dim_hierarchy)
        self.col_rename_map = self.dim_hier.col_rename_map
        self.dim_val_map = dim_val_map
        self.helper = SharedFn()
        self.hit_row_limit = False

        self.sp = sp

        self.use_max_sql_gen = is_using_max_sql_gen()

        self.pull_data_func = df_provider.pull_data if df_provider and hasattr(df_provider, "pull_data") else pull_data

        # database connection
        if sql_exec:
            self.con = sql_exec
        else:
            raise exit_with_status("sql_exec is required. Please use a Connector of type 'duckdb', 'parquet', or 'db'.")

    def check_row_limit(self, df: pd.DataFrame):
        if not self.hit_row_limit:
            self.hit_row_limit = len(df) == self.con.limit

    def _get_breakouts(self, table, metric, breakouts, period_filters, query_filters, table_specific_filters, top_n, view="", tokens=[]):

        # get owner dim to ensure always included in breakouts
        owner_node = self.dim_hier.get_lowest_level_ms_dim_filter(query_filters)

        owner_dim = owner_node['col'] if owner_node else None
        owner_val = owner_node['val'] if owner_node else None
        self._owner_dim = self.helper.get_dimension_prop(owner_dim, self.dim_props).get("label", owner_dim) if owner_dim else None

        dfs = []
        for breakout in breakouts:

            # if breakout is competition/owner dim, remove owner_dim from query_filters
            breakout_filters = query_filters.copy()
            if breakout == owner_dim:
                breakout_filters = [f for f in query_filters if f['col'] != owner_dim]

            # split query filters into tokens and non-tokens
            tokens = [f['val'] for f in breakout_filters if is_filter_token(f['val']) and f['col'] == breakout]
            breakout_filters = [f for f in breakout_filters if not is_filter_token(f['val'])]

            additional_filters = table_specific_filters.get(breakout, table_specific_filters.get('default', []))

            # current period
            df_curr = self.pull_data_func(metrics=[metric], breakouts=[breakout], filters=breakout_filters+additional_filters+[period_filters[0]])
            self.check_row_limit(df_curr)
            df_curr.set_index(breakout, inplace=True)

            # compare period
            df_prev = self.pull_data_func(metrics=[metric], breakouts=[breakout], filters=breakout_filters+additional_filters+[period_filters[1]])
            self.check_row_limit(df_prev)
            df_prev.set_index(breakout, inplace=True)

            # combine current and compare period dfs
            df = pd.concat([df_curr, df_prev], axis=1)
            df.index.name = 'dim_value'
            df.index = df.index.astype(str)
            df.columns = ['curr', 'prev']

            # convert curr and prev to float
            df['curr'] = df['curr'].astype(float)
            df['prev'] = df['prev'].astype(float)

            # create rank cols
            df['rank_curr'] = df['curr'].rank(ascending=False)
            df['rank_prev'] = df['prev'].rank(ascending=False)
            df['rank_change'] = df['rank_prev'] - df['rank_curr']

            df['diff'] = df['curr'] - df['prev']
            df['diff_pct'] = df['diff'].div(np.abs(df['prev'].replace(0, np.nan)), fill_value=0)
            df['dim'] = breakout

            df['section'] = '2.competitors' if breakout == owner_dim else '3.breakouts'

            # order
            if "<growing>" in tokens:
                df = df.sort_values(by='diff', ascending=False)
            elif "<declining>" in tokens:
                df = df.sort_values(by='diff', ascending=True)
            else:
                df = df.sort_values(by='rank_curr')

            if top_n:
                # get top N rows and ensure owner_val is included
                if breakout == owner_dim:
                    owner_val_lower = owner_val.lower()
                    # check if the owner_val is already in the top_n rows
                    if owner_val_lower in df.index[:top_n]:
                        df = df.head(top_n)
                    else:
                        # if not, include the owner_val row and then get the top_n rows
                        owner_row = df[df.index.str.lower() == owner_val_lower]
                        top_rows = df.head(top_n)
                        df = pd.concat([top_rows, owner_row]).drop_duplicates().head(top_n+1)
                else:
                    df = df.head(top_n)

            dfs.append(df)

        df = pd.concat(dfs)

        # get absolute diff
        df['abs_diff'] = df['diff'].abs()

        return df

    def col_name_mapping(self, hier, mapping):
        if not hier:
            return mapping
        else:
            for dim in hier:
                mapping[dim['col']] = dim['name']
                if dim['children']:
                    self.col_name_mapping(dim["children"], mapping)
        return mapping

    def get_dim_map_display_value(self, dim, val):
        return self.dim_val_map.get((dim, val), val)

    def title_from_filters(self, q_filters):
        if q_filters:
            # TODO: Handle titles for metric filters
            dim_filters, metric_filters = old_split_dim_and_metric_filters(q_filters, self.dim_props)
            subject_items = [
                f"{self.helper.get_dimension_prop(f['col'], self.dim_props).get('label', f['col'])} {f['op']} {self.get_dim_map_display_value(f['col'], f['val'])}"
                for f in dim_filters
            ]
            return ", ".join(subject_items)
        else:
            return "all data"

    def get_section_facts(self, df, section, member_type):
        """ sections: 1.subject, 2.competitors, 3.breakouts """
        df = df.copy()
        df.reset_index(inplace=True)
        # get section data
        cols = ['dim', 'dim_value', 'curr', 'diff', 'rank_curr', 'rank_change', 'abs_diff']
        cols = [col for col in cols if col in df.columns]
        df = df[df['section'] == section].copy()[cols]

        if not df.empty:
            # limit to top 3 rows for each dim by absolute diff
            df_top_3 = df.groupby('dim').apply(lambda x: x.nlargest(
                3, 'abs_diff')).reset_index(drop=True)

            # add ranking for top 3 abs_diff
            df_top_3['rank'] = df_top_3.groupby('dim')['abs_diff'].rank(ascending=False, method='first', na_option="bottom")

            # add notes for top 3 abs_diff '#1 rank by sales diff'
            df_top_3['note'] = df_top_3.apply(lambda x: f"#{int(x['rank'])} rank by {self.target_metric['label']} diff", axis=1)

            # filter main df to get highest growing and highest declining dim value for each dim
            df_high_growing = df[df['diff'] > 0].groupby('dim').apply(lambda x: x.nlargest(1, 'abs_diff')).reset_index(drop=True)
            df_high_declining = df[df['diff'] < 0].groupby('dim').apply(lambda x: x.nlargest(1, 'abs_diff')).reset_index(drop=True)

            # add notes for highest growing and declining
            df_high_growing['note'] = 'Highest growing'
            df_high_declining['note'] = 'Highest declining'

            # combine top 3 abs_diff, highest growing and declining
            df = pd.concat([df_top_3, df_high_growing, df_high_declining])

            # combine notes if there are multiple notes for the same dim
            df['note'] = df.groupby(['dim', 'dim_value'])['note'].transform(lambda x: ', '.join(x))

            # drop duplicates
            df.drop_duplicates(subset=['dim', 'dim_value'], inplace=True)

            df = df.sort_values(by=['dim', 'abs_diff'], ascending=[True, False])

            # apply formatting
            if self.use_default_met_props:
                df['curr'] = df['curr'].apply(fmt_num)
                df['diff'] = df['diff'].apply(fmt_sign_int)
            else:
                fmt = self.target_metric.get("fmt")
                df['curr'] = df['curr'].apply(lambda x: self.helper.get_formatted_num(x, fmt))
                df['diff'] = df['diff'].apply(lambda x: self.helper.get_formatted_num(x, fmt))

            df['rank_curr'] = df['rank_curr'].apply(fmt_num)
            if 'rank_change' in df.columns:
                df['rank_change'] = df['rank_change'].apply(fmt_sign_int)

            # rename columns & drop abs_diff
            df = df[cols+['note']].rename(columns={
                'dim': 'level',
                'dim_value': member_type,
                'curr': self.target_metric["label"],
                'diff': 'change'
            }).drop(columns=['abs_diff'])

        return df

    def _add_sparklines(self, breakout_df, table, target_metric, period_filters, query_filters, table_specific_filters, period_col_granularity, two_year_filter=None, view=""):
        # get owner dim to ensure always included in breakouts
        owner_node = self.dim_hier.get_lowest_level_ms_dim_filter(query_filters)
        owner_dim = owner_node['col'] if owner_node else None

        if two_year_filter:
            period_filter = two_year_filter
            period_col = period_filter['col']
        else:
            # first period filter must be current period, second is compare period
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

        # initialize sparkline col
        breakout_df['sparkline'] = None

        # create sparklines for each breakout
        for breakout in breakout_df['dim'].unique():
            # get all competition values
            breakout_filters = query_filters.copy()
            if breakout == owner_dim:
                breakout_filters = [f for f in query_filters if f['col'] != owner_dim]

            # add filters for every dim val in breakout_df to limit rows being pulled
            dim_vals = breakout_df[breakout_df['dim'] == breakout].index.to_list()

            if self.use_max_sql_gen:
                breakout_filters.append({'col': breakout, 'op': 'in', 'val': dim_vals})
            else:
                for val in dim_vals:
                    breakout_filters.append({'col': breakout, 'op': '=', 'val': val})

            additional_filters = table_specific_filters.get(breakout, table_specific_filters.get('default', []))

            breakout_trend_df = self.pull_data_func(metrics=[target_metric], breakouts=[period_col, breakout], filters=breakout_filters+additional_filters+[period_filter], order_cols=[{"col": period_col, "direction": "ASC"}])
            breakout_trend_df = breakout_trend_df.pivot(index=period_col, columns=breakout, values=target_metric["name"]).reset_index()

            breakout_df.loc[breakout_df['dim'] == breakout, 'sparkline'] = breakout_df[breakout_df['dim'] == breakout].index.to_series().apply(lambda x: sparkline(breakout_trend_df[x].to_list()) if x in breakout_trend_df else sparkline([np.nan]))

        return breakout_df

    def create_header(self, metric, breakouts, period_filters, query_filters, growth_type, top_n):
        def create_and_rename_filter_dict(filters, rename_map):
            # create dict {col: [val1, val2, val3, etc]}
            filter_dict = {}
            for f in filters:
                if f['col'] not in filter_dict:
                    filter_dict[f['col']] = []
                filter_dict[f['col']].append(f['val'])

            # rename the keys
            keys_list = list(filter_dict.keys())
            for col in keys_list:
                new_col = rename_map.get(col, col)
                if new_col != col:
                    filter_dict[new_col] = filter_dict.pop(col)

            return filter_dict

        def get_header(breakout_str, metric, filter_str, date_range_str, growth_type):
            header = f"""
            <p style="font-size: 18px; font-weight: bold; color: #333; margin: 0px;">
                {breakout_str} Drivers of {metric}
            </p>
            <p style="font-size: 12px; color: #888; margin: 2.5px 0px 0px;">
            {filter_str}
            </p>
            <p style="font-size: 12px; color: #888; margin: 2.5px 0px 0px;">
                Driver Analysis • {date_range_str} • {growth_type.upper()}
            </p>
            <br>
            """
            return header


        # get non token filters
        non_token_filters = [f for f in query_filters if not is_filter_token(f['val'])]
        # TODO: handle filter_str for metric filters
        non_token_dim_filters, metric_filters = old_split_dim_and_metric_filters(non_token_filters, self.dim_props)
        filter_dict = create_and_rename_filter_dict(non_token_dim_filters, self.col_rename_map)

        # create string representation for header. Format should be col: val1, val2, val3 • col2: val1, val2, etc
        filter_str = " • ".join([f"{k}: {', '.join(v)}" for k, v in filter_dict.items()])
        if filter_str:
            filter_str = f"For {filter_str}"

        if isinstance(period_filters[0]['val'], list):
            date_range_str = f"{period_filters[0]['val'][0]} to {period_filters[0]['val'][1]}"
        else:
            date_range_str = f"{period_filters[0]['val']} to {period_filters[1]['val']}"
        date_range_str = date_range_str.replace("'", "")

        # get token filters
        token_filters = [f for f in query_filters if is_filter_token(f['val'])]
        token_dict = create_and_rename_filter_dict(token_filters, self.col_rename_map)

        headers = {}
        for breakout in breakouts:
            # rename breakout
            breakout = self.col_rename_map.get(breakout, breakout)

            top_n_str = f"Top {top_n}" if top_n else "Top"

            if breakout in token_dict:
                if "<growing>" in token_dict[breakout]:
                    breakout_str = f"{top_n_str} Growing {breakout}"
                elif "<declining>" in token_dict[breakout]:
                    breakout_str = f"{top_n_str} Declining {breakout}"
                elif "<all>" in token_dict[breakout]:
                    breakout_str = f"{top_n_str} {breakout}"
            else:
                breakout_str = f"{top_n_str} {breakout}"

            metric_name = metric["name"]
            headers[breakout] = get_header(breakout_str, metric_name, filter_str, date_range_str, growth_type)

        return headers

    def get_display_tables(self, viz_func=None):
        df = self._df.copy()
        tables = None
        dims = list(df["dim"].unique())

        if self.dim_hier:
            # display according to the dim hierarchy ordering
            ordering_dict = {value: index for index, value in enumerate(self.dim_hier.get_hierarchy_ordering())}
            # rename cols to dim labels
            ordering_dict = {self.helper.get_dimension_prop(k, self.dim_props).get("label", k): v for k, v in ordering_dict.items()}
            # sort dims by hierarchy order
            dims.sort(key=lambda x: (ordering_dict.get(x, len(ordering_dict)), x))

        comp_dim = None
        if self._owner_dim:
            comp_dim = next((d for d in dims if d.lower() == self._owner_dim.lower()), None)

        if comp_dim:
            comp_df = df[df["dim"] == comp_dim]
            comp_df["followup_nl"] = "can you please run the same analysis for '" + comp_df.index.astype(str) + "' " + comp_df["dim"].astype(str) + "?"
            viz_func(comp_df, f"Benchmark")

        if viz_func:
            for dim in dims:
                if dim != comp_dim:
                    dim_df = df[df["dim"] == dim]
                    dim_df["followup_nl"] = "can you please add '" + dim_df.index.astype(str) + "' " + dim_df["dim"].astype(str) + " filter?"
                    viz_func(dim_df, f"{dim}")
        else:
            tables = df

        return tables

    def get_breakouts_table_jinja(self):
        return """
            <head>
                <meta charset="UTF-8">
                <style>
                body {
                    font-size:12pt;
                    font-family: Arial, sans-serif;
                    line-height:1.5;
                }
                table {
                    border: 0;
                    width: 100%;
                    table-layout: fixed;
                    font-size: 10pt;
                    border-collapse: collapse;
                }
                thead {
                    background: #EEE;
                    height: 25px;
                }
                tbody tr:nth-child(odd) {
                    background-color: #f9f9f9;
                }
                tbody tr:nth-child(even) {
                    background-color: #ffffff;
                }
                th {
                    text-align: right;
                    height: 30px;
                    padding-right: 5px;
                }
                tr {
                    display: table-row;
                }
                td {
                    text-align: right;
                    padding-right: 5px;
                }
                .daily_values {

                }
                .table-wrapper {
                    width: 100%;
                    overflow-x: auto;
                }
                table {
                    min-width: 100%;
                    width: auto;
                    font-size: 10pt;
                    border-collapse: collapse;
                }
                th {
                    border-bottom: 1px solid #c0c0c0;
                    padding: 8px;
                    text-align: right;
                    white-space: nowrap;
                }
                td {
                    border-bottom: 1px solid #e0e0e0;
                    padding: 8px;
                    text-align: right;
                    white-space: nowrap; /* Prevent content wrapping */
                }
                th {
                    background-color: #f2f2f2;
                }
                </style>
            </head>
            <body>
            <div class="table-wrapper">
                    <table>
                        <thead>
                        <tr>
                            <th style="text-align:left;">{{df['dim'].iloc[0]}}</th>
                            <th>Value</th>
                            <th>Prev Value</th>
                            <th>Change</th>
                            <th>% Growth</th>
                            <th>Rank (+/-)</th>
                            {% if include_sparklines %}<th>Sparkline</th>{% endif %}
                        </tr>
                        </thead>
                        <tbody>
                        {% for dim_value, row in df.iterrows() %}
                        <tr>
                        {% set dim_value_safe = dim_value | safe %}
                            <td style="text-align:left; padding-left: 20px;">{{ sfn.click_html(dim_value_safe, row.get('followup_nl', dim_value_safe)) }}</td>
                            <td>{{ sfn.get_formatted_num(row['curr'], da.metric['fmt']) }}</td>
                            <td>{{ sfn.get_formatted_num(row['prev'], da.metric['fmt']) }}</td>
                            <td>{{ sfn.get_formatted_num(row['diff'], da.metric['fmt']) }}</td>
                            <td>{{ sfn.get_formatted_num(row['diff_pct'], da.metric['growth_fmt']) }}</td>
                            <td>{{ row['rank_curr'] | int  }}{% if row['rank_change'] %} ({{ row['rank_change'] | fmt_sign_num }}){% endif %} </td>
                            {% if include_sparklines %}<td><img height="35px" src="data:image/png;base64,{{ row['sparkline'] }}"/></td>{% endif %}
                        </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
            </body>
        """

    def run(self, table, metric, breakouts, period_filters, query_filters=[], table_specific_filters={}, top_n=5, include_sparklines=True, two_year_filter=None, period_col_granularity='day', view="", growth_type="", metric_props={}, dim_props={}):
        owner_node = self.dim_hier.get_lowest_level_ms_dim_filter(query_filters)
        owner_dim = owner_node['col'] if owner_node else None

        self.dim_props = dim_props

        if top_n == 1:
            top_n = 5

        # flag if metric_props is empty, for backwards compatibility
        self.use_default_met_props = False
        if not metric_props:
            self.use_default_met_props = True

        # set target metric to first metric
        self.target_metric = self.helper.get_metric_prop(metric, metric_props)

        if not self.target_metric.get("sql") and not self.target_metric.get("name") and self.target_metric.get("is_share"):
            share_metric = self.target_metric.get("label", self.target_metric.get("name"))
            raise exit_with_status(f"Tell the user that '{share_metric}' metric is not supported in Metric Driver skill. Advise the user to ask for a market share drivers skill or to try a new question. Please do not make choice on user’s behalf or provide suggestion outside of this instruction.")

        breakout_df = None

        if owner_dim and owner_dim not in breakouts:
            breakouts.append(owner_dim)

        if breakouts:
            # breakout table
            breakout_df = self._get_breakouts(
                table = table,
                metric = self.target_metric,
                breakouts = breakouts,
                period_filters = period_filters,
                query_filters = query_filters,
                table_specific_filters = table_specific_filters,
                top_n = top_n,
                view = view
            )

        # add sparklines
        if include_sparklines:
            breakout_df = self._add_sparklines(
                breakout_df = breakout_df,
                table = table,
                target_metric = self.target_metric,
                period_filters = period_filters,
                query_filters = query_filters,
                table_specific_filters = table_specific_filters,
                period_col_granularity = period_col_granularity,
                two_year_filter = two_year_filter,
                view = view
            )

        # format dim labels
        breakout_df['dim'] = breakout_df['dim'].apply(lambda x: self.helper.get_dimension_prop(x, self.dim_props).get("label", x))

        self._df = breakout_df
        self.subject_title = self.title_from_filters(query_filters)
        self.competitor_facts = self.get_section_facts(breakout_df, '2.competitors', "competitor")
        self.breakout_facts = self.get_section_facts(breakout_df, '3.breakouts', "driver")

        self.headers = self.create_header(self.target_metric, breakouts, period_filters, query_filters, growth_type, top_n)

        self.default_table_template = self.get_breakouts_table_jinja()

        return breakout_df
