
from ar_analytics import BreakoutAnalysis
from overproof_utilities import OverproofSharedFn, calculate_market_share_denominator 
from ar_analytics.helpers.utils import is_filter_token, HIGHEST_GROWING, FASTEST_GROWING, FASTEST_DECLINING, HIGHEST_DECLINING, BIGGEST, SMALLEST
import pandas as pd

class OverproofBreakoutAnalysis(BreakoutAnalysis):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = OverproofSharedFn()
        self.rank_share_within_by_market = False

    def get_sort_details(self, period_filters, breakout, special_tokens, top_n_direction):
        breakout_token = [t for t in special_tokens if t['col'] == breakout]

        sort_dir = top_n_direction
        sort_metric = self.first_metric

        if self.sort_rule:
            sort_hint = self.sort_rule
        elif breakout_token:
            sort_hint = self.match_token(str(breakout_token[0]['val']))
        else:
            sort_hint = "None"

        self.sort_hint = sort_hint
        # only change defaults for following conditions
        if len(period_filters) > 1:
            if self.match_token(FASTEST_GROWING) in sort_hint:
                if self.first_metric in self.hide_pct_mets:
                    sort_metric = sort_metric + "_diff"
                else:
                    sort_metric = sort_metric + "_diff_pct"
                sort_dir = "top"
            elif self.match_token(HIGHEST_GROWING) in sort_hint:
                sort_metric = sort_metric + "_diff"
                sort_dir = "top"
            elif self.match_token(FASTEST_DECLINING) in sort_hint:
                if self.first_metric in self.hide_pct_mets:
                    sort_metric = sort_metric + "_diff"
                else:
                    sort_metric = sort_metric + "_diff_pct"
                sort_dir = "bottom"
            elif self.match_token(HIGHEST_DECLINING) in sort_hint:
                sort_metric = sort_metric + "_diff"
                sort_dir = "bottom"
            elif self.match_token(BIGGEST) in sort_hint:
                sort_metric = sort_metric + "_curr"
                sort_dir = "top"
            elif self.match_token(SMALLEST) in sort_hint:
                sort_metric = sort_metric + "_curr"
                sort_dir = "bottom"
            else:
                sort_metric = sort_metric + "_curr"
        else:
            if self.match_token(BIGGEST) in sort_hint:
                sort_metric = sort_metric
                sort_dir = "top"
            elif self.match_token(SMALLEST) in sort_hint:
                sort_metric = sort_metric
                sort_dir = "bottom"
            else:
                sort_metric = sort_metric

        if self.is_share_first:

            # if share is the first metric, and sort by diff then use share diff
            if sort_metric.endswith("_diff") or sort_metric.endswith("_diff_pct"):
                sort_metric = f"{self.first_share_metric}_diff"
            elif breakout in self.sort_by_denom:
                #### SVCS-86: Sort on underlying metric overwrite
                # for share within metrics, sort by the denominator or share metric
                if self.rank_share_within_by_market:
                    sort_metric = f"{sort_metric}__market"
                else:
                    sort_metric = self.first_share_metric
                ####

        sort_asc = (sort_dir.lower() == 'bottom')
        print(
            f"breakout_token: {breakout_token}, breakout: {breakout}, sort_hint: {sort_hint}, sort_metric: {sort_metric}, sort_asc: {sort_asc}, sort_dir: {sort_dir}")
        return sort_metric, sort_asc

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
