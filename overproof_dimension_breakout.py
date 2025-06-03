
from ar_analytics import BreakoutAnalysis
from overproof_utilities import OverproofSharedFn, calculate_market_share_denominator 
from ar_analytics.helpers.utils import is_filter_token
import pandas as pd

class OverproofBreakoutAnalysis(BreakoutAnalysis):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = OverproofSharedFn()

    # Overwriting so that the share for count metrics is calculated correctly for count metrics.
    def get_share_totals(self, table, metrics, breakouts, period_filters, query_filters, table_specific_filters, view):

        def get_cache_key(filters, breakout=None):

            # custom sorting key that handles None values
            def sort_key(item):
                col, op, val = item
                return (col, op, (val is not None, val))

            sorted_filters = tuple(sorted(frozenset((f['col'], f['op'], str(f['val'])) for f in filters), key=sort_key))
            if breakout:
                return sorted_filters + tuple(breakout)
            return sorted_filters

        breakout_filters = query_filters.copy()
        market_filters = [f for f in breakout_filters if
                          not is_filter_token(f['val']) and f['col'] not in self.dim_hier.owner_cols]
        
        if breakouts:
            dfs = []
            totals_cache = {}
            for breakout in breakouts:
                breakout_label = self.helper.get_dimension_prop(breakout, self.dim_props).get("label", breakout)
                # check if filters are the same for numerator and denominator
                # if it's the same then calculate contribution to total
                if market_filters == breakout_filters:
                    groupby = []
                    self.contributions.append(breakout_label)
                    subject_breakout = breakout
                # only breakout the denominator if it is not an owner column
                elif breakout in self.dim_hier.owner_cols:
                    groupby = []
                    self.contributions.append(breakout_label)
                    subject_breakout = breakout
                else:
                    groupby = [breakout]
                    self.share_within.append(breakout_label)
                    self.sort_by_denom.append(breakout)
                    subject_filters = [f for f in breakout_filters if
                          not is_filter_token(f['val']) and f['col'] in self.dim_hier.owner_cols]
                    subject_breakout = subject_filters[0]['col'] if subject_filters else None


                additional_filters = table_specific_filters.get(breakout, table_specific_filters.get('default', []))
                cache_key = get_cache_key(market_filters + additional_filters, breakout=groupby)

                if cache_key in totals_cache:
                    df = totals_cache[cache_key].copy(deep=True)
                    df["dim"] = breakout
                else:
                    df_curr = calculate_market_share_denominator(
                        pull_data_func = self.pull_data_func,
                        metrics=metrics,
                        breakouts=groupby,
                        filters=market_filters + additional_filters + ([period_filters[0]] if period_filters else []),
                        subject_breakout=subject_breakout
                    )

                    self.check_row_limit(df_curr)
                    df_curr["dim"] = breakout

                    if len(period_filters) > 1:
                        df_prev = calculate_market_share_denominator(
                            pull_data_func = self.pull_data_func,
                            metrics=metrics,
                            breakouts=groupby,
                            filters=market_filters + additional_filters + [period_filters[1]],
                            subject_breakout=subject_breakout
                        )
                        self.check_row_limit(df_prev)
                        df_prev["dim"] = breakout
                        df = pd.merge(df_curr, df_prev, on=["dim"] + groupby, suffixes=('_curr', '_prev'))
                    else:
                        df = df_curr.copy()
                    df = self._calc_breakout_metrics(df, metrics)
                    # if denominator is an owner column, rename it to dim_member
                    if groupby:
                        df = df.rename(columns={breakout: "dim_member"})
                    else:
                        df['dim_member'] = 'Total'
                    totals_cache[cache_key] = df.copy(deep=True)
                dfs.append(df)
            df = pd.concat(dfs, ignore_index=True)
        else:
            subject_filters = [f for f in breakout_filters if
                    not is_filter_token(f['val']) and f['col'] in self.dim_hier.owner_cols]
            subject_breakout = subject_filters[0]['dim'] if subject_filters else None
            additional_filters = table_specific_filters.get('default', [])
            df_curr = calculate_market_share_denominator(
                pull_data_func = self.pull_data_func,
                metrics=metrics,
                filters=market_filters + additional_filters + ([period_filters[0]] if period_filters else []),
                subject_breakout=subject_breakout
            )
            self.check_row_limit(df_curr)
            df_curr["dim"] = "Total"
            if len(period_filters) > 1:
                df_prev = calculate_market_share_denominator(
                    pull_data_func = self.pull_data_func,
                    metrics=metrics,
                    filters=market_filters + additional_filters + [period_filters[1]],
                    subject_breakout=subject_breakout
                )
                self.check_row_limit(df_prev)
                df_prev["dim"] = "Total"
                df = pd.merge(df_curr, df_prev, on="dim", suffixes=('_curr', '_prev'))
                df = self._calc_breakout_metrics(df, metrics)
            else:
                df = self._calc_breakout_metrics(df_curr, metrics)

            df['dim_member'] = 'Total'

        return df
