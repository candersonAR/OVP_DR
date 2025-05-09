

from ar_analytics import DriverAnalysis
from ar_analytics.breakout_drivers import BreakoutDrivers
from ar_analytics.metric_tree import MetricTreeAnalysis
from overproof_utilities import OverproofSharedFn

class OverproofDriverAnalysis(DriverAnalysis):

    def __init__(self, dim_hierarchy, dim_val_map={}, sql_exec=None, constrained_values={}, compare_date_warning_msg=None, df_provider=None, sp=None):
        self.mta = OverproofMetricTreeAnalysis(sql_exec, df_provider=df_provider, sp=sp)
        self.ba = OverproofBreakoutDrivers(dim_hierarchy, dim_val_map, sql_exec, df_provider=df_provider, sp=sp)
        self.helper = OverproofSharedFn()
        self.allowed_metrics = constrained_values.get("metric", [])
        self.alloed_breakouts = constrained_values.get("breakout", [])
        self.notes = []
        self.compare_date_warning_msg = compare_date_warning_msg
        self.sp=sp


class OverproofMetricTreeAnalysis(MetricTreeAnalysis):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = OverproofSharedFn()


class OverproofBreakoutDrivers(BreakoutDrivers):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = OverproofSharedFn()