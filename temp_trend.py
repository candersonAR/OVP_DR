
from collections import defaultdict
from ar_analytics.trend import AdvanceTrend, GROWTH, DELTA
from ar_analytics.helpers.utils import Connector
from overproof_utilities import MenuColNames, OverproofSharedFn

class OverproofTemporaryAdvanceTrend(AdvanceTrend):
    def __init__(self, table: str, sql_exec: Connector, time: dict, dim_hierarchy: dict = {}, constrained_values={}, max_num_charts=10, df_provider=None):
        super().__init__(table, sql_exec, time, dim_hierarchy, constrained_values, max_num_charts, df_provider)
        self.helper = OverproofSharedFn()

    # Overwriting so that sales_uplift is considered a calculated metric
    # This will make it so pull_data is called to recalculate the total for sales uplift
    def get_metric_sql(self, metric):
        calculated_metrics, non_calculated_metrics = None, None
        if metric.get("sql") and metric.get("col") or metric.get("name") in [MenuColNames.MENU_UPLIFT_METRIC.value, MenuColNames.COCKTAIL_UPLIFT_METRIC.value, MenuColNames.SINGLE_SPIRIT_UPLIFT_METRIC.value]:
            calculated_metrics = metric
        elif metric.get("col"):
            non_calculated_metrics = metric["name"]
        return calculated_metrics, non_calculated_metrics
