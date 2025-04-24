from typing import Optional
from ar_analytics.helpers.utils import pull_data, exit_with_status
from overproof_utilities import MenuColNames
import pandas as pd
import numpy as np

class DataProvider(object):
    def __init__(self):
        # make sure this is correct
        # self.menu_dataset = "c50c3d81-682f-463e-a924-747d62e62318" # Ar Max Menu Table
        # self.depletion_dataset = "d91a492a-d62a-405e-90d8-0b9a3984f5ea" # Ar Max Depletions

        self.menu_dataset = "326b5bd5-55bd-49bd-a2e5-f601b1c25d52" # Snowflake Ar Max Menu Table
        self.depletion_dataset = "88a8a548-b4bc-4800-8397-e7d7f8d0bdb4" # Snowflake Ar Max Depletions

        self.cross_dims = [
            MenuColNames.COCKTAIL_NAME_COL.value, 
            MenuColNames.COCKTAIL_STYLE_COL.value, 
            MenuColNames.COCKTAIL_FAMILY_COL.value, 
            MenuColNames.COCKTAIL_GROUP_COL.value, 
            MenuColNames.COCKTAIL_FLAVORS_COL.value, 
            MenuColNames.COCKTAIL_DERIVED_FROM_COL.value, 
            MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value,
            MenuColNames.INGREDIENT_OF_COCKTAIL_GROUP_COL.value,
            MenuColNames.INGREDIENT_OF_COCKTAIL_STYLE_COL.value,
            MenuColNames.INGREDIENT_OF_COCKTAIL_FAMILY_COL.value,
            # MenuColNames.MENU_ITEM_NAME_COL.value, 
            # MenuColNames.MENU_ITEM_TYPE_COL.value
        ]
        # todo: sales uplift
        self.sales_uplift_metrics = [MenuColNames.SALES_UPLIFT_METRIC.value]
        # joining dimensions (lowest common granularity) between menu and depletions data
        self.common_dims = [MenuColNames.VENUE_ID_COL.value, MenuColNames.PRODUCT_ID_COL.value]
        self.menu_metrics = [MenuColNames.MENU_PLACEMENTS_METRIC.value, MenuColNames.VENUE_PLACEMENTS_METRIC.value]
        self.depletions_metrics = [MenuColNames.SOLD_9LE_METRIC.value, MenuColNames.SOLD_CASES_METRIC.value]
        self.psudo_join_col = "join_col"
        self.depletions_agg_dict = {MenuColNames.SOLD_9LE_METRIC.value: np.sum, MenuColNames.SOLD_CASES_METRIC.value: np.sum}
        self.max_time_dimensions = [MenuColNames.MAX_TIME_MONTH_COL.value, MenuColNames.MAX_TIME_QUARTER_COL.value, MenuColNames.MAX_TIME_YEAR_COL.value]
        
    def pull_data(
            self,
            metrics,
            breakouts=None,
            filters=None,
            order_cols=None,
            query_row_limit=None
        ) -> pd.DataFrame:

        df = pd.DataFrame()
        # todo: handle order cols, only used in trend to determine top n

        breakouts = breakouts or []

        menu_metrics = [m for m in metrics if m.get("name") in self.menu_metrics]
        depletion_metrics = [m for m in metrics if m.get("name") in self.depletions_metrics]
        sales_uplift_metrics = [m for m in metrics if m.get("name") in self.sales_uplift_metrics]

        if filters:
            cocktail_filter_dims = [f["col"] for f in filters if f["col"] in self.cross_dims]
        else:
            cocktail_filter_dims = []

        if breakouts:
            cocktail_dims = [b for b in breakouts if b in self.cross_dims]
        else:
            cocktail_dims = []

        time_period_dims = [d for d in breakouts if d in self.max_time_dimensions]

        is_cross_query = sales_uplift_metrics or (depletion_metrics and (cocktail_dims or cocktail_filter_dims))

        dfs = []
        if menu_metrics:
            menu_df = pull_data(metrics=menu_metrics,
                                breakouts=breakouts,
                                filters=filters,
                                order_cols=order_cols,
                                query_row_limit=query_row_limit,
                                dataset_id=self.menu_dataset)
            print(f"total_rows: {len(menu_df)}")
            dfs.append(menu_df)

        if depletion_metrics and not (cocktail_dims or cocktail_filter_dims):
            depletion_df = pull_data(metrics=depletion_metrics,
                                     breakouts=breakouts,
                                     filters=filters,
                                     order_cols=order_cols,
                                     query_row_limit=query_row_limit,
                                     dataset_id=self.depletion_dataset)
            print(f"total_rows: {len(depletion_df)}")
            dfs.append(depletion_df)

        if is_cross_query:

            qualifier_joining_dims = cocktail_dims
            if sales_uplift_metrics:
                qualifier_joining_dims = qualifier_joining_dims + time_period_dims + [MenuColNames.VENUE_ID_COL.value]
            if (depletion_metrics and (cocktail_dims or cocktail_filter_dims)):
                qualifier_joining_dims = qualifier_joining_dims + [dim for dim in self.common_dims if dim not in qualifier_joining_dims]

            # limiting the data to only venues and product relevant for cocktails
            qualifier_df = pull_data(metrics=[],
                                     breakouts=qualifier_joining_dims,
                                     filters=filters,
                                     query_row_limit=10000000, # hardcoded, can get pretty large
                                     dataset_id=self.menu_dataset)
            print(f"total_rows: {len(qualifier_df)}")

            qualifier_df = qualifier_df.drop_duplicates()

            if sales_uplift_metrics:

                uplift_common_dims = [MenuColNames.VENUE_ID_COL.value] + time_period_dims

                # only concerned with venues for sales uplift
                qualifier_df = qualifier_df[cocktail_dims + uplift_common_dims].drop_duplicates()

                # remove cocktail dims since it's not available on depletion data
                depl_dims = [b for b in breakouts if b not in cocktail_dims and b not in uplift_common_dims]
                depl_fils = [f for f in filters if f["col"] not in self.cross_dims] if filters else []
                
                sales_uplift_df = pull_data(
                    metrics=sales_uplift_metrics,
                    breakouts=depl_dims + uplift_common_dims,
                    filters=depl_fils,
                    order_cols=order_cols,
                    dataset_id=self.depletion_dataset
                )

                # get the total average sales uplift across the time period breakout
                # time_period_dims = [d for d in depl_dims if d in self.max_time_dimensions]
                sales_uplift_total_avg_agg_dict = {sales_uplift_metrics[0].get("name"): np.mean}
                if time_period_dims:
                    total_avg_sales_uplift_df = sales_uplift_df.groupby(time_period_dims).agg(sales_uplift_total_avg_agg_dict).reset_index()
                else:
                    total_avg_sales_uplift_df = sales_uplift_df.agg(sales_uplift_total_avg_agg_dict).to_frame().T
                total_avg_sales_uplift_df = total_avg_sales_uplift_df.rename(columns={sales_uplift_metrics[0].get("name"): "total_avg"})

                # join the sales uplift df with the qualifier df on the common dims
                sales_uplift_df = pd.merge(sales_uplift_df, qualifier_df, on=uplift_common_dims, how='inner')

                # join the sales uplift df with the total avg sales uplift df on the time period dims, aggregate by time period dims
                if time_period_dims:
                    sales_uplift_df = pd.merge(sales_uplift_df, total_avg_sales_uplift_df, on=time_period_dims, how='left')
                else:
                    # total_avg_sales_uplift_df should be a scalar
                    sales_uplift_df["total_avg"] = total_avg_sales_uplift_df.iloc[0]["total_avg"]

                sales_uplift_joined_agg_dict = {sales_uplift_metrics[0].get("name"): np.mean, "total_avg": np.sum}
                agg_dims = cocktail_dims + time_period_dims + depl_dims
                if "date_column" in sales_uplift_df.columns and time_period_dims: 
                    # keep the trend date_column, which will mirror the time_period dim used
                    agg_dims.append("date_column")

                if agg_dims:
                    sales_uplift_df = sales_uplift_df.groupby(agg_dims).agg(sales_uplift_joined_agg_dict).reset_index()
                else:
                    sales_uplift_df = sales_uplift_df.agg(sales_uplift_joined_agg_dict).to_frame().T
                
                # calculate the sales uplift
                sales_uplift_df[MenuColNames.SALES_UPLIFT_METRIC.value] = sales_uplift_df[MenuColNames.SALES_UPLIFT_METRIC.value] / sales_uplift_df["total_avg"]

                # drop the total_avg column
                sales_uplift_df = sales_uplift_df.drop(columns=["total_avg"])
                dfs.append(sales_uplift_df)

            if (depletion_metrics and (cocktail_dims or cocktail_filter_dims)):

                # remove cocktail dims since it's not available on depletion data
                depl_dims = [b for b in breakouts if b not in cocktail_dims]
                depl_fils = [f for f in filters if f["col"] not in self.cross_dims] if filters else []
                pre_depletion_df = pull_data(metrics=depletion_metrics,
                                            breakouts=depl_dims + self.common_dims,
                                            filters=depl_fils,
                                            order_cols=order_cols,
                                            query_row_limit=query_row_limit,
                                            dataset_id=self.depletion_dataset)
                print(f"total_rows: {len(pre_depletion_df)}")

                # this join should add all the dims as breakouts with cocktails dim coming from qualifier_df
                # this might do intended cross join for product used in multiple cocktails
                depletion_df = pd.merge(pre_depletion_df, qualifier_df, on=self.common_dims, how='inner')
                depl_mets = [m.get("name") for m in depletion_metrics]
                agg_dict = {k: v for k, v in self.depletions_agg_dict.items() if k in depl_mets}
                if breakouts:
                    depletion_df = depletion_df.groupby(breakouts).agg(agg_dict).reset_index()
                else:
                    depletion_df = depletion_df.agg(agg_dict).to_frame().T
                dfs.append(depletion_df)

        if len(dfs) > 1:
            df = dfs[0]
            if not breakouts:
                df[self.psudo_join_col] = "total"
            for d in dfs[1:]:
                if breakouts:
                    df = pd.merge(df, d, on=breakouts, how="left", suffixes=("", "__y"))
                else:
                    d[self.psudo_join_col] = "total"
                    df = pd.merge(df, d, on=[self.psudo_join_col], how="left", suffixes=("", "__y"))
        elif len(dfs) == 1:
            df = dfs[0]

        drop_cols = [self.psudo_join_col] + [c for c in df.columns if c.endswith("__y")]
        drop_cols = [c for c in drop_cols if c in df.columns]
        if drop_cols:
            df = df.drop(columns=drop_cols)

        if "date_column" in df.columns:
            df = df.sort_values(by=["date_column"], ascending=True)

        return df
    
    # TODO: Remove once overproof env is upgraded to a newer version of ar-analytics, specifically after commit 1113da3bd0ff68da9314a3aad8166ebd4e4a4672
    def breakout_analysis(self,
                          metrics,
                          breakouts=None,
                          filters=None,
                          order_cols=None,
                          query_row_limit=None):
        
        df = self.pull_data(metrics, breakouts, filters, order_cols, query_row_limit)
        
        return df
    
    # TODO: Remove once overproof env is upgraded to a newer version of ar-analytics, specifically after commit 1113da3bd0ff68da9314a3aad8166ebd4e4a4672
    def metric_tree_analysis(self,
                            metrics,
                            breakouts=None,
                            filters=None,
                            order_cols=None,
                            query_row_limit=None):
        
        df = self.pull_data(metrics, breakouts, filters, order_cols, query_row_limit)
        
        return df
    