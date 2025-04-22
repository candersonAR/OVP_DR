from collections import defaultdict

import pandas as pd

from ar_analytics.helpers.utils import Connector, TemplateParameterSetup, get_viz_header, \
    is_filter_token, get_date_label_str, NO_LIMIT_N, SharedFn, exit_with_status, \
    old_split_dim_and_metric_filters, old_get_filters_headline, SkillPlatform, fmt_sign_num
# from ar_analytics.breakout_drivers import BreakoutDrivers
from temp_breakout_drivers import BreakoutDrivers
from temp_metric_tree import MetricTreeAnalysis
# from ar_analytics.metric_tree import MetricTreeAnalysis


class DriverAnalysis:
    def __init__(self, dim_hierarchy, dim_val_map={}, sql_exec:Connector=None, constrained_values={}, compare_date_warning_msg=None, df_provider=None, sp=None):
        self.mta = MetricTreeAnalysis(sql_exec, df_provider=df_provider, sp=sp)
        self.ba = BreakoutDrivers(dim_hierarchy, dim_val_map, sql_exec, df_provider=df_provider, sp=sp)
        self.helper = SharedFn()
        self.allowed_metrics = constrained_values.get("metric", [])
        self.alloed_breakouts = constrained_values.get("breakout", [])
        self.notes = []
        self.compare_date_warning_msg = compare_date_warning_msg
        self.sp=sp

    @classmethod
    def from_env(cls, env, df_provider=None):

        if env is None:
            raise exit_with_status("env is required")

        cls.env = env

        return cls(
            dim_hierarchy=env.driver_analysis_parameters["dim_hierarchy"],
            sql_exec=env.driver_analysis_parameters["con"],
            constrained_values=env.driver_analysis_parameters["constrained_values"],
            compare_date_warning_msg=env.driver_analysis_parameters["compare_date_warning_msg"],
            df_provider=df_provider,
            sp=env.sp
        )
    
    def get_warning_messages(self):

        warning_messages = []

        if self.ba.hit_row_limit:
            msg = f'The following analysis has been limited to {self.helper.get_formatted_num(self.ba.con.limit, ",.0f")} rows which may impact the accuracy of the observations made.'
            warning_messages.append(msg)

        if self.compare_date_warning_msg:
            warning_messages.append(self.compare_date_warning_msg)

        warning_message = ' '.join(warning_messages)
        if warning_message:
            warning_message = f"⚠ {warning_message}"

        return warning_message

    def process_filters(self, filters, breakouts, node_limit):

        dim_filters, metric_filters = old_split_dim_and_metric_filters(filters, self.dim_props)

        # create dict of filters
        filters_dict = defaultdict(list)
        for f in dim_filters:
            filters_dict[f['col']].append((f['op'], f['val']))

        # for the filters that arent breakouts, only keep the first filter
        dim_filters = []
        for col, ops_vals in filters_dict.items():
            for i, (op, val) in enumerate(ops_vals):
                if col in breakouts or i == 0 or op.lower() not in ["=", "in"]:
                    dim_filters.append({'col': col, 'op': op, 'val': val})
                else:
                    col_label = self.helper.get_dimension_prop(col, self.dim_props).get('label', col)
                    exit_with_status(f"Please explain to the use that this specific analysis supports only one {col_label} filter at a time. Please ask the user to update his request to focus on a particular {col_label}.")

        # if no breakouts specified and dim_hierarchy is not empty, then use the hierarchy for breakouts
        if not breakouts:
            if self.ba.dim_hier.dim_hierarchy:
                filter_dims = [f['col'] for f in dim_filters if not is_filter_token(f['val'])]
                breakouts = self.ba.dim_hier.get_next_level_keys(filter_dims, include_children=True, node_limit=node_limit) + self.ba.dim_hier.find_unmentioned_top_level_keys(filter_dims)

        filter_str = ", ".join([f"{self.helper.get_dimension_prop(f['col'], self.dim_props).get('label', f['col'])} {f['op']} {f['val']}" for f in dim_filters])
        if not filter_str:
            filter_str = "no filters used"
        self.notes.append(f"The analysis was run using only these filters: {filter_str}")

        filters = dim_filters + metric_filters
        return filters, breakouts

    def check_required_params(self, metric, period_filters, breakouts, metric_props, dim_props, filter_dims):
        available_metrics = self.allowed_metrics or list(metric_props.keys())
        available_dims = self.alloed_breakouts or list(dim_props.keys())

        if filter_dims:
            available_dims = [d for d in available_dims if d not in filter_dims]

        if not metric:
            raise exit_with_status(f"Ask user to provide at least one metric. Please do not make choice on user's behalf. Some examples of metrics are: {available_metrics}.")
        elif metric not in available_metrics:
            raise exit_with_status(f"Ask user to specify a valid metric. Please do not make choice on user's behalf. Please ask user to chose from {available_metrics}.")
        if not period_filters:
            raise exit_with_status("Ask user to provide a time range. Please do not make choice on user’s behalf.")
        if not breakouts:
            raise exit_with_status(f"Ask user to provide at least one breakout dimension. Please do not make choice on user's behalf. Some examples of breakout dimensions are: {available_dims[:5]}.")

    def get_analysis_message(self, metric, filters, date_labels):

        # get labels

        met_label = metric.get("label", metric.get("name"))

        filter_labels = []
        dim_filters, metric_filters = old_split_dim_and_metric_filters(filters, dim_props=self.dim_props)
        for f in dim_filters:
            dim_dict = self.helper.get_dimension_prop(f['col'], self.dim_props)
            filter_labels.append(f"{dim_dict.get('label', dim_dict.get('name'))} {f['op']} {f['val']}")

        for f in metric_filters:
            met_dict = self.helper.get_metric_prop(f['name'], self.metric_props)
            filter_labels.append(f"{met_dict.get('label', met_dict.get('name'))} {f['op']} {f['val']}")

        date_label = get_date_label_str(date_labels, prefix="")

        # form message

        analysis_message = f"Analysis ran for metric {met_label}"
        if filter_labels:
            analysis_message += f" filtered to {self.helper.and_comma_join(filter_labels)}"

        if date_label:
            analysis_message += f" for the period {date_label}"

        return analysis_message

    def get_metric_tree_jinja(self):
        return """
            {% macro bold_if_depth_zero(value, depth) %}
                {% if depth == 0 %}
                    <b>{{ value }}</b>
                {% else %}
                    {{ value }}
                {% endif %}
            {% endmacro %}

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
                th:nth-child(1) {
                    width: 200px;
                }
                th {
                    text-align: right;
                    height: 30px;
                    padding: 8px;
                    white-space: nowrap;
                }
                tr {
                    display: table-row;
                }
                td {
                    text-align: right;
                    padding: 8px;
                    //min-width:100px;
                    text-align: right;
                    white-space: nowrap; /* Prevent content wrapping */
                }
                th:first-child, td:first-child {
                    position: sticky;
                    left:2;
                    z-index: 1;
                }
                th:first-child::before, td:first-child::before {
                    content: "";
                    position: absolute;
                    top: 0;
                    left: -2px;
                    bottom: 0;
                    width: 2px;
                    background-color: white;
                    z-index: 5;
                }

                th:first-child::after, td:first-child::after {
                    content: "";
                    position: absolute;
                    top: 0;
                    right: -2px;
                    bottom: 0;
                    width: 2px;
                    background-color: white;
                    z-index: 5;
                }
                th:first-child{
                    background: #EEE;
                }
                tbody tr:nth-child(odd) td:first-child {
                    background-color: #f9f9f9;
                }
                tbody tr:nth-child(even) td:first-child {
                    background-color: #ffffff;
                }
            </style>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th></th>
                            <th>Value</th>
                            <th>Prev Value</th>
                            <th>Change</th>
                            <th>% Growth</th>
                            {% if 'impact' in df.columns %}<th>{{ da.mta.impact_col }}</th>{% endif %}
                            {% if include_sparklines %}<th>Sparkline</th>{% endif %}
                        </tr>
                    </thead>
                    <tbody>
                        {% for metric, row in df.iterrows() %}
                            {% set depth = row.depth | default("NaN") %}
                            <tr>
                                <td style='text-align:left; {% if depth != "NaN" %}padding-left:{{ 10 * depth }}px;{% endif %}'>{% if depth == 0 %}<b>{{ sfn.get_metric_prop(metric, metric_props).get("label", metric) }}</b>{% else %}{{ sfn.get_metric_prop(metric, metric_props).get("label", metric) }}{% endif %}</td>
                                <td>{{ bold_if_depth_zero(sfn.get_formatted_num(row['curr'], sfn.get_metric_prop(metric, metric_props)['fmt']), depth) }}</td>
                                <td>{{ bold_if_depth_zero(sfn.get_formatted_num(row['prev'], sfn.get_metric_prop(metric, metric_props)['fmt']), depth) }}</td>
                                <td>{{ bold_if_depth_zero(sfn.get_formatted_num(row['diff'], sfn.get_metric_prop(metric, metric_props)['fmt']), depth) }}</td>
                                <td>{{ bold_if_depth_zero(sfn.get_formatted_num(row['growth'], sfn.get_metric_prop(metric, metric_props)['growth_fmt']), depth) }}</td>
                                {% if 'impact' in row %}<td>{{ bold_if_depth_zero(sfn.get_formatted_num(row['impact'], da.mta.impact_format), depth) }}</td>{% endif %}
                                {% if include_sparklines %}<td><img height="35px" src="data:image/png;base64,{{ row['sparkline'] }}"/></td>{% endif %}
                            </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        """

    def run_from_env(self):

        if self.env is None:
            raise exit_with_status("self.env is required")

        da_result = self.run(
            table = self.env.driver_analysis_parameters.get("table"),
            metrics = self.env.driver_analysis_parameters.get("metric"),
            breakouts = self.env.driver_analysis_parameters.get("breakouts"),
            period_filters = self.env.driver_analysis_parameters.get("period_filters"),
            query_filters = self.env.driver_analysis_parameters.get("query_filters"),
            top_n = self.env.driver_analysis_parameters.get("limit_n"),
            driver_metrics = self.env.driver_analysis_parameters.get("driver_metrics"),
            period_col_granularity=self.env.driver_analysis_parameters.get("period_col_granularity"),
            growth_type = self.env.driver_analysis_parameters.get("growth_type"),
            metric_props = self.env.metric_props,
            dim_props = self.env.dim_props,
            include_sparklines = self.env.driver_analysis_parameters.get("include_sparklines"),
            two_year_filter = self.env.driver_analysis_parameters.get("two_year_filter"),
            view = self.env.driver_analysis_parameters.get("derived_sql_table"),
            date_labels = self.env.driver_analysis_parameters.get("date_labels"),
            impact_formulas = self.env.driver_analysis_parameters.get("impact_formulas"),
        )

        # handle parameter bubble updates after running analysis
        if self.top_n:
            if "ParameterDisplayDescription" in self.env.driver_analysis_parameters:
                self.env.driver_analysis_parameters["ParameterDisplayDescription"].\
                    update({'limit_n': f"Top {str(self.top_n)}"})
            else:
                self.env.driver_analysis_parameters["ParameterDisplayDescription"] = {'limit_n': f"Top {str(self.top_n)}"}

        self.paramater_display_infomation = self.env.driver_analysis_parameters.get("ParameterDisplayDescription", {})

        # set env variables
        self.env.viz__header = self.viz_header

        return da_result

    def run(self, table, metrics, breakouts, period_filters, query_filters=[], driver_metrics=[], top_n=5, include_sparklines=False, two_year_filter=None, period_col_granularity='day', view="", growth_type="", date_labels={}, metric_props={}, dim_props={}, node_limit=None, impact_formulas={}):

        self.metric_props = metric_props
        self.dim_props = dim_props
        self.include_sparklines = include_sparklines

        if top_n == 1:
            top_n = 5

        metric = metrics[0] if metrics and isinstance(metrics, list) else metrics
        metric = metric.lower()

        query_filters, breakouts = self.process_filters(query_filters, breakouts, node_limit)

        filter_dims = []
        if query_filters:
            filter_dims = [f.get("col") for f in query_filters]

        self.check_required_params(metric, period_filters, breakouts, metric_props, dim_props, filter_dims)

        title_metric = self.helper.get_metric_prop(metric, metric_props).get("label", metric)

        if len(query_filters) > 0:
            title = old_get_filters_headline(query_filters, additional_values=[title_metric], metric_props=metric_props, dim_props=dim_props)
        else:
            title = f"Total • {title_metric}"

        if not driver_metrics:
            driver_metrics = [{"metric": metric, "parent_metric": None}]

        driver_metrics = [{
            "metric": m["metric"].lower(),
            "parent_metric": m["parent_metric"].lower() if m["parent_metric"] else m["parent_metric"],
            "peer_metrics": m.get("peer_metrics", [])
        } for m in driver_metrics]

        metric_df = self.mta.run(
            table = table,
            metrics = [m["metric"] for m in driver_metrics],
            period_filters = period_filters,
            query_filters = query_filters,
            driver_metrics = driver_metrics,
            view = view,
            include_sparklines = include_sparklines,
            two_year_filter = two_year_filter,
            period_col_granularity = period_col_granularity,
            metric_props = metric_props,
            add_impacts = True,
            impact_formulas = impact_formulas
        )

        breakout_df = self.ba.run(
            table = table,
            metric = metric,
            breakouts = breakouts,
            period_filters = period_filters,
            query_filters = query_filters,
            top_n = top_n,
            include_sparklines = include_sparklines,
            period_col_granularity = period_col_granularity,
            two_year_filter=two_year_filter,
            view = view,
            growth_type = growth_type,
            metric_props = metric_props,
            dim_props = dim_props
        )

        if breakout_df.empty:
            raise exit_with_status("Report did not run: Please tell the user there is no data available for the selected set of filter.  Recommend changing the filter criteria or ask a different question to proceed.")

        self.metric = self.ba.target_metric
        self.subject_title = self.ba.subject_title

        date_str = get_date_label_str(date_labels) if date_labels else ""
        self.viz_header = get_viz_header(title=title, subtitle=f"Driver Analysis{date_str}", warning_messages=self.get_warning_messages())

        # set subject fact to the first row of metric_df
        self.subject_fact = {"status": "ok", "df": metric_df.iloc[0:1]}

        if self.mta.impact_df_col in metric_df.columns:
            if metric_df[self.mta.impact_df_col].isnull().all():
                metric_df = metric_df.drop(columns=[self.mta.impact_df_col])
            else:
                metric_df[self.mta.impact_df_col] = metric_df[self.mta.impact_df_col].fillna("--")

        self.default_metric_tree_template = self.get_metric_tree_jinja()

        self.competitor_facts = self.ba.competitor_facts
        self.breakout_facts = self.ba.breakout_facts
        self.breakout_headers = self.ba.headers

        self.notes.append(self.get_analysis_message(metric_props.get(metric), query_filters, date_labels))
        if self.compare_date_warning_msg:
            self.notes.append(self.compare_date_warning_msg)
        self.df_notes = pd.DataFrame({"Note to the assistant:":self.notes})

        # updated params, need for updating chat pills
        self.top_n = top_n

        self.title = title
        self.subtitle = f"Driver Analysis{date_str}"

        # save it as members for use in the display tables
        self._metric_df = metric_df
        self._breakout_df = breakout_df

        return {"metric_df": metric_df, "breakout_df": breakout_df}
    
    def get_display_tables(self):
        metric_df = self._metric_df.copy()
        breakout_df = self._breakout_df.copy()

        # Define required columns for metric_df
        metric_tree_required_columns = ["curr", "prev", "diff", "growth"]
        if self.include_sparklines:
            metric_tree_required_columns.append("sparkline")

        if "impact" in metric_df.columns:
            metric_tree_required_columns.append("impact")

        # Filter metric_df to include only the required columns
        metric_df = metric_df[metric_tree_required_columns]

        # Apply formatting for metric_df
        for col in ["curr", "prev", "diff", "growth"]:
            metric_df[col] = metric_df.apply(
                lambda row: self.helper.get_formatted_num(
                    row[col],
                    self.helper.get_metric_prop(row.name, self.metric_props).get("fmt",
                                                                                 "") if col != "growth" else self.helper.get_metric_prop(
                        row.name, self.metric_props).get("growth_fmt", "")
                ), axis=1
            )

        if "impact" in metric_df.columns:
            metric_df["impact"] = metric_df.apply(
                lambda row: self.helper.get_formatted_num(row["impact"], self.mta.impact_format), axis=1
            )
        # rename columns
        metric_df = metric_df.rename(
            columns={'curr': 'Value', 'prev': 'Prev Value', 'diff': 'Change', 'growth': '% Growth'})

        metric_df = metric_df.reset_index()

        # indent non target metric
        metric_df["index"] = metric_df["index"].apply(lambda x: f"  {x}" if x != self.mta.target_metric else x)

        metric_df = metric_df.rename(columns={"index": ""})

        # Define required columns for breakout_df
        breakout_required_columns = ["curr", "prev", "diff", "diff_pct", "rank_change"]
        if self.include_sparklines:
            breakout_required_columns.append("sparkline")

        breakout_dfs = {}

        # Apply formatting for breakout_df
        for col in ["curr", "prev", "diff", "diff_pct"]:
            breakout_df[col] = breakout_df.apply(
                lambda row: self.helper.get_formatted_num(row[col],
                                                          self.ba.target_metric["fmt"] if col != "diff_pct" else
                                                          self.ba.target_metric["growth_fmt"]),
                axis=1
            )

        # Format rank column
        breakout_df["rank_curr"] = breakout_df["rank_curr"]
        breakout_df["rank_change"] = breakout_df.apply(lambda row: f"{int(row['rank_curr'])} ({fmt_sign_num(row['rank_change'])})"
                                                    if (row['rank_change'] and pd.notna(row['rank_change']) and row['rank_change'] != 0)
                                                    else row['rank_curr'], axis=1)
        breakout_df = breakout_df.reset_index()

        breakout_dims = list(breakout_df["dim"].unique())
        if self.ba.dim_hier:
            # display according to the dim hierarchy ordering
            ordering_dict = {value: index for index, value in enumerate(self.ba.dim_hier.get_hierarchy_ordering())}
            # rename cols to dim labels
            ordering_dict = {self.helper.get_dimension_prop(k, self.dim_props).get("label", k): v for k, v in ordering_dict.items()}
            # sort dims by hierarchy order
            breakout_dims.sort(key=lambda x: (ordering_dict.get(x, len(ordering_dict)), x))

        comp_dim = None
        if self.ba._owner_dim:
            comp_dim = next((d for d in breakout_dims if d.lower() == self.ba._owner_dim.lower()), None)

        if comp_dim:
            breakout_dims = [comp_dim] + [x for x in breakout_dims if x != comp_dim]

        for dim in breakout_dims:
            b_df = breakout_df[breakout_df["dim"] == dim]
            if str(dim).lower() == str(comp_dim).lower():
                viz_name = "Benchmark"
            else:
                viz_name = dim
            b_df = b_df.rename(columns={'dim_value': dim})
            b_df = b_df[[dim] + breakout_required_columns]

            # rename columns
            b_df = b_df.rename(
                columns={'curr': 'Value', 'prev': 'Prev Value', 'diff': 'Change', 'diff_pct': '% Growth',
                         'rank_change': 'Rank Change'})
            breakout_dfs[viz_name] = b_df

        return {"viz_metric_df": metric_df, "viz_breakout_dfs": breakout_dfs}

class DriverAnalysisTemplateParameterSetup(TemplateParameterSetup):

    def __init__(self, sp=None, env=None):
        if sp is None:
            sp = SkillPlatform()

        super().__init__(sp=sp)
        self.map_env_values(env=env)

        # set the skill platform on env
        env.sp = sp

    """
    Creates parameters necessary to run the driver analysis skill from the copilot skill parameter values and dataset.
    These are set on the env under driver_analysis_parameters, ie env.driver_analysis_parameters.

    Adds UI bubbles for certain parameters.
    """
    def map_env_values(self, env=None):

        """
        This function currently hardcodes the following names of the copilot skill variables in the templates, specifially
        - metric
        - breakouts
        - periods
        - date_col
        - limit_n
        - growth_type
        TODO: Create way to reference these dynamically from the copilot skill.
        """

        if env is None:
            raise exit_with_status("env namespace is required.")

        driver_analysis_parameters = {}
        pills = {}

        ## Setup DB

        database_id = self.dataset_metadata.get("database_id")
        driver_analysis_parameters["table"] = self.dataset_metadata.get("sql_table")
        driver_analysis_parameters["derived_sql_table"] = self.dataset_metadata.get("derived_table_sql") or ""
        dataset_misc_info = self.dataset_metadata.get("misc_info") or {}
        driver_analysis_parameters["impact_formulas"] = dataset_misc_info.get("impact_formulas") or {}

        driver_analysis_parameters["con"] = Connector("db", database_id=database_id, sql_dialect=self.dataset_metadata.get("sql_dialect"), limit=self.sql_row_limit)

        _, driver_analysis_parameters["dim_hierarchy"] = self.sp.data.get_dimension_hierarchy()
        _, driver_analysis_parameters["driver_metrics"] = self.sp.data.get_metric_hierarchy()
        driver_analysis_parameters["constrained_values"] = self.constrained_values

        ## Map Env Variables

        # Get metric_props, dim_props, setting on env since the chart templates reference these

        env.metric_props = self.get_metric_props()
        env.dim_props = self.get_dimension_props()

        # Get metrics and metric pills

        driver_analysis_parameters["metric"] = env.metric
        metric_pills = self.get_metric_pills(env.metric, env.metric_props)

        # Get filters by dimension
        driver_analysis_parameters["query_filters"], query_filters_pills = self.parse_dimensions(env)

        # Parse breakout dims to the sql columns
        driver_analysis_parameters["breakouts"], breakout_pills = self.parse_breakout_dims(env.breakouts)

        # guardrails for unsupported calculated filters
        calculated_metric_filters = env.calculated_metric_filters if hasattr(env, "calculated_metric_filters") else None
        query, llm_notes, _, _ = self.get_metric_computation_filters([env.metric], calculated_metric_filters, "None", env.metric_props)
        if query:
            self.get_unsupported_filter_message(llm_notes, 'metric drivers')

        ### Period Handling ###

        default_granularity = self.dataset_metadata.get("default_granularity")
        compare_date_warning_msg = None

        if not self.is_period_table:
            start_date, end_date, comp_start_date, comp_end_date = self.handle_periods_and_comparison_periods(env.periods, env.growth_type, allowed_tokens=['<no_period_provided>', '<since_launch>'])

            # date/period column metadata. Assumes the date column is a date type
            period_col = env.date_col if hasattr(env, "date_col") and env.date_col else self.get_period_col()

            if not period_col:
                exit_with_status("A date column must be provided.")

            # create period filters using start date and end date, and comparison start and end dates
            period_filters = []

            if start_date and end_date:
                period_filters.append(
                    { "col": period_col, "op": "BETWEEN", "val": f"'{start_date}' AND '{end_date}'"}
                )

            if comp_start_date and comp_end_date:
                period_filters.append(
                    { "col": period_col, "op": "BETWEEN", "val": f"'{comp_start_date}' AND '{comp_end_date}'" }
                )
                if self.is_date_range_completely_out_of_bounds(comp_start_date, comp_end_date):
                    time_granularity = self.dataset_metadata.get("default_granularity")
                    start_period = self.helper.format_date_from_time_granularity(self.dataset_metadata["min_date"], time_granularity)
                    end_period = self.helper.format_date_from_time_granularity(self.dataset_metadata["max_date"], time_granularity)
                    msg = [f"Please inform the user that the analysis cannot run because data is unavailable for the required {env.growth_type} comparison period."]
                    msg.append(f"Data is only available from {start_period} to {end_period}.")
                    msg.append(f"Ask the user to modify the date range to ensure it aligns with an available {env.growth_type} comparison period within this timeframe.")
                    msg.append("Please do not make any assumptions on behalf of the user.")
                    exit_with_status(" ".join(msg))
                elif self.is_date_range_partially_out_of_bounds(comp_start_date, comp_end_date):
                    compare_date_warning_msg = "Data is only avaiable for partial comparison period. This gap might impact the analysis results and insights."

            two_year_filter = None

            # format dates after adding them to the period filters

            start_date = self.helper.format_date_from_time_granularity(start_date, default_granularity)
            end_date = self.helper.format_date_from_time_granularity(end_date, default_granularity)
            comp_start_date = self.helper.format_date_from_time_granularity(comp_start_date, default_granularity)
            comp_end_date = self.helper.format_date_from_time_granularity(comp_end_date, default_granularity)

            date_labels = {"start_date": start_date, "end_date": end_date, "compare_start_date": comp_start_date, "compare_end_date": comp_end_date}

        else:
            _, periods_in_year = self.sp.data.get_periods_in_year()
            date_filters, _ = self.get_time_variables(env.periods)
            period_filters, date_labels = self.get_period_filters(sql_con=driver_analysis_parameters["con"],
                                                        date_filters=date_filters,
                                                        growth_type=env.growth_type,
                                                        sparkline_n_year=2)

            if period_filters:
                two_year_filter = period_filters[-1]
                period_filters = period_filters[:-1]
            else:
                two_year_filter = None

            print("period_filters")
            print(period_filters)

            if str(env.growth_type).lower() != "none" and not date_labels.get("compare_start_date"):
                msg = ["Please inform the user that the analysis cannot run because data is unavailable for the required year-over-year (Y/Y) comparison period."]
                msg.append(f"Data is only available from {date_labels.get('data_start_date')} to {date_labels.get('data_end_date')}.")
                msg.append(f"Ask the user to modify the date range to ensure it aligns with an available {env.growth_type} comparison period within this timeframe.")
                msg.append("Please do not make any assumptions on behalf of the user.")
                exit_with_status(" ".join(msg))
            elif self.is_period_date_partially_out_of_bounds(period_filters):
                compare_date_warning_msg = "Data is only avaiable for partial comparison period. This gap might impact the analysis results and insights."

            start_date = date_labels.get("start_date")
            end_date = date_labels.get("end_date")
            comp_start_date = date_labels.get("compare_start_date")
            comp_end_date = date_labels.get("compare_end_date")

        # Set the trend date parameters
        driver_analysis_parameters["date_labels"] = date_labels
        driver_analysis_parameters["period_filters"] = period_filters
        driver_analysis_parameters["period_col_granularity"] = "day"
        driver_analysis_parameters["two_year_filter"] = two_year_filter
        driver_analysis_parameters["compare_date_warning_msg"] = compare_date_warning_msg

        # convert limit_n to an int
        if hasattr(env, "limit_n") and env.limit_n:
            if env.limit_n == NO_LIMIT_N:
                driver_analysis_parameters["limit_n"] = None
            else:
                driver_analysis_parameters["limit_n"] = self.convert_to_int(env.limit_n)

        # set growth type

        driver_analysis_parameters["growth_type"] = env.growth_type

        # use sparklines

        env.include_sparklines = True # must be set since the chart references env.include_sparklines
        driver_analysis_parameters["include_sparklines"] = env.include_sparklines

        ## add UI bubbles

        if metric_pills:
            pills["metric"] = f"Metric: {self.helper.and_comma_join(metric_pills)}"
        if query_filters_pills:
            pills["filters"] = f"Filter: {self.helper.and_comma_join(query_filters_pills)}"
        if breakout_pills:
            pills["breakout"] = f"Breakout: {self.helper.and_comma_join(breakout_pills)}"
        if start_date and end_date:
            if start_date == end_date:
                pills["period"] = f"Period: {start_date}"
            else:
                pills["period"] = f"Period: {start_date} to {end_date}"
        if comp_start_date and comp_end_date:
            if comp_start_date == comp_end_date:
                pills["compare_period"] = f"Compare Period: {comp_start_date}"
            else:
                pills["compare_period"] = f"Compare Period: {comp_start_date} to {comp_end_date}"
        if hasattr(env, "growth_type"):
            if str(env.growth_type).lower() in ["p/p", "y/y"]:
                pills["growth_type"] = f"Growth Type: {str(env.growth_type)}"

        driver_analysis_parameters["ParameterDisplayDescription"] = pills

        ## Set the driver analysis parameters
        env.driver_analysis_parameters = driver_analysis_parameters
