
from collections import defaultdict
from ar_analytics.trend import AdvanceTrend, GROWTH, DELTA
from ar_analytics.helpers.utils import Connector

class OverproofTemporaryAdvanceTrend(AdvanceTrend):
    def __init__(self, table: str, sql_exec: Connector, time: dict, dim_hierarchy: dict = {}, constrained_values={}, max_num_charts=10, df_provider=None):
        super().__init__(table, sql_exec, time, dim_hierarchy, constrained_values, max_num_charts, df_provider)

    def get_dynamic_layout_chart_vars(self):
        rendered_charts = defaultdict(dict)
        growth_type = str(self.env.growth_type).lower()
        # this is looping through tabs
        for name in self.display_charts.keys():
            display_df = self.display_charts[name]['df']
            footer = self.display_charts[name].get("footnote")
            if growth_type in ["y/y", "p/p"]:
                if self.env.breakouts:
                    unique_metrics = list(display_df['metric'].unique())
                    chart_vars = {"hide_growth_chart": False, "hide_absolute_series_name": False, "footer": footer, "hide_footer": False if footer else True}
                    for metric in unique_metrics:
                        df = display_df[display_df['metric'] == metric]

                        ### Only change is adding handling for Growth and the PoP versions
                        if metric.endswith("YoY Difference") or metric.endswith("PoP Difference"):
                            series_type = 'difference'
                        elif metric.endswith("YoY % Change") or metric.endswith("YoY Growth") or metric.endswith("PoP % Change") or metric.endswith("PoP Growth"):
                            series_type = 'growth'
                        else:
                            series_type = 'absolute'
                        ###

                        chart_vars[f"{series_type}_metric_name"] = metric

                        # collect vars
                        chart_name = df["chart_name"].iloc[0]
                        chart_obj = self.display_charts[chart_name]
                        x_axis = chart_obj['xAxis']
                        y_axis = []
                        for axis in chart_obj['axis_info'][series_type]["yaxis"]:
                            y_axis.append({
                                "title": axis['title'],
                                "labels": {
                                    "format": self.ar_utils.python_to_highcharts_format(axis['fmt']).get('value_format')},
                                "opposite": True if axis['opposite'] else False
                            })

                        series = []

                        unique_metrics = df[['metric', 'fmt']].drop_duplicates()
                        for metric_row in unique_metrics.itertuples():
                            filtered_df = df[df['metric'] == metric_row.metric]
                            variable_cols = []
                            for col in filtered_df.columns:
                                if col not in ['date_column', self.date_alias, 'month', 'metric', 'fmt', 'chart_name']:
                                    variable_cols.append(col)

                            for col in variable_cols:
                                if col not in ['date_column', self.date_alias, 'chart_name']:
                                    series_name = col
                                    point_formatter = self.ar_utils.python_to_highcharts_format(metric_row.fmt).get('point_y_format')
                                    dataLabels = {
                                        "enabled": True if self.show_labels else False,
                                        "align": "center",
                                        "verticalAlign": "top",
                                        "y": -20,
                                        "format": point_formatter
                                    },

                                    series.append({"name": series_name,
                                                   "id": f"{series_name}_{metric_row.metric}",
                                                   "fmt": metric_row.fmt,
                                                   "data": self.helper.replace_nans_with_string_nan(df[col].to_list()),
                                                   "yAxis": 0,
                                                   "tooltip": {"pointFormat": "<b>{series.name}</b>: " + point_formatter},
                                                   "dataLabels": dataLabels,
                                                   "pointPadding": 0})

                        chart_vars[f"{series_type}_series"] = series
                        chart_vars[f"{series_type}_x_axis_categories"] = x_axis
                        chart_vars[f"{series_type}_y_axis"] = y_axis
                    rendered_charts[name] = chart_vars
                else:
                    growth_metrics = [m for m in display_df.columns if m.endswith("_growth")]
                    difference_metrics = [m for m in display_df.columns if m.endswith("_delta")]
                    absolute_metrics = [m.replace("_delta", "") for m in difference_metrics]
                    series_map = {"absolute": absolute_metrics, "difference": difference_metrics, "growth": growth_metrics}
                    chart_vars = {"hide_growth_chart": False, "hide_absolute_series_name": False, "footer": footer, "hide_footer": False if footer else True}
                    for series_type, metrics in series_map.items():
                        keep_cols = ['date_column', 'month', 'quarter', 'year', 'chart_name'] + metrics
                        keep_cols = [col for col in keep_cols if col in display_df.columns]
                        df = display_df[keep_cols]

                        chart_name = df["chart_name"].iloc[0]
                        chart_obj = self.display_charts[chart_name]
                        x_axis = chart_obj['xAxis']
                        y_axis = []
                        for axis in chart_obj['axis_info'][series_type]["yaxis"]:
                            y_axis.append({
                                "title": axis['title'],
                                "labels": {
                                    "format": self.ar_utils.python_to_highcharts_format(axis['fmt']).get('value_format')},
                                "opposite": True if axis['opposite'] else False
                            })
                        series = []
                        for col in df.columns:
                            if col not in ['date_column', self.date_alias, 'month', 'metric', 'fmt', 'chart_name']:
                                series_name = chart_obj['name'] if chart_obj['name'] else self.helper.get_metric_prop(col, self.metric_props)['label']
                                num_format = chart_obj['fmt'] if chart_obj['fmt'] else self.helper.get_metric_prop(col, self.metric_props)['fmt']

                                data = self.helper.replace_nans_with_string_nan(df[col].to_list())
                                point_formatter = self.ar_utils.python_to_highcharts_format(num_format).get('point_y_format')

                                dataLabels = {
                                    "enabled": True if self.show_labels else False,
                                    "align": "center",
                                    "verticalAlign": "top",
                                    "y": -20,
                                    "format": point_formatter
                                },

                                series.append({"name": series_name,
                                               "id": f"{series_name}",
                                               "data": data,
                                               "yAxis": chart_obj["yaxis_index"][col],
                                               "tooltip": {"pointFormat": "<b>{series.name}</b>: " + point_formatter},
                                               "dataLabels": dataLabels,
                                               "pointPadding": 0})

                        chart_vars[f"{series_type}_series"] = series
                        chart_vars[f"{series_type}_x_axis_categories"] = x_axis
                        chart_vars[f"{series_type}_y_axis"] = y_axis
                        chart_vars[f"{series_type}_metric_name"] = series_name if len(metrics) == 1 else series_type.title()

                    rendered_charts[name] = chart_vars
            else:
                chart_vars = {"hide_growth_chart": True, "hide_absolute_series_name": True, "footer": footer, "hide_footer": False if footer else True}
                display_df['chart_name'] = name
                df = display_df

                chart_name = df["chart_name"].iloc[0]
                chart_obj = self.display_charts[chart_name]
                x_axis = df[self.date_alias].to_list()
                y_axis = []
                for axis in chart_obj["yaxis"]:
                    y_axis.append({"title": axis['title'], "labels": {
                        "format": self.ar_utils.python_to_highcharts_format(axis['fmt']).get('value_format')},
                                   "opposite": True if axis['opposite'] else False})

                variable_cols = []
                for col in df.columns:
                    if col not in ['date_column', self.date_alias, 'month', 'metric', 'fmt', 'chart_name']:
                        variable_cols.append(col)

                series = []
                series_type = "absolute"
                for col in variable_cols:
                    if col not in ['date_column', self.date_alias, 'chart_name', 'fmt']:
                        if not chart_obj["dim_breakout"]:
                            line_name = chart_obj['name'] if chart_obj['name'] else \
                                self.helper.get_metric_prop(col, self.metric_props)['label']
                            num_format = chart_obj['fmt'] if chart_obj['fmt'] else \
                                self.helper.get_metric_prop(col, self.metric_props)['fmt']
                        else:
                            num_format = chart_obj['fmt'] if chart_obj['fmt'] else \
                                self.helper.get_metric_prop(col, self.metric_props)['fmt']
                            line_name = chart_obj['name'] if chart_obj['name'] else col

                        point_format = self.ar_utils.python_to_highcharts_format(num_format).get('point_y_format')

                        series.append({"name": line_name,
                                       "data": self.helper.replace_nans_with_string_nan(df[col].to_list()),
                                       "yAxis": chart_obj["yaxis_index"][col] if not chart_obj["dim_breakout"] else 0,
                                       "tooltip": {"pointFormat": "<b>{series.name}</b>: " + point_format},
                                       "dataLabels": {"enabled": True if self.show_labels else False,
                                                      "align": "center",
                                                      "verticalAlign": "top",
                                                      "y": -20,
                                                      "format": point_format},
                                       "pointPadding": 0
                                       })

                chart_vars[f"{series_type}_series"] = series
                chart_vars[f"{series_type}_x_axis_categories"] = x_axis
                chart_vars[f"{series_type}_y_axis"] = y_axis
                chart_vars[f"{series_type}_metric_name"] = ""

                rendered_charts[name] = chart_vars

        return rendered_charts