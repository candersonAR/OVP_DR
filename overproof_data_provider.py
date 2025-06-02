from typing import Optional
from ar_analytics.helpers.utils import pull_data, exit_with_status, PreQueryOperator
from overproof_utilities import MenuColNames
import pandas as pd
import numpy as np
import time

import logging
_logger = logging.getLogger(__name__)

from ar_analytics.helpers.utils import _process_filters, AnswerRocketClient, get_dataset_id
import time

class DataProvider(object):
    def __init__(self):
        # make sure this is correct
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
        self.sales_uplift_metrics = [MenuColNames.COCKTAIL_UPLIFT_METRIC.value, MenuColNames.MENU_UPLIFT_METRIC.value, MenuColNames.SINGLE_SPIRIT_UPLIFT_METRIC.value]
        # joining dimensions (lowest common granularity) between menu and depletions data
        self.common_dims = [MenuColNames.VENUE_ID_COL.value, MenuColNames.PRODUCT_ID_COL.value]
        self.menu_metrics = [MenuColNames.MENU_PLACEMENTS_METRIC.value, MenuColNames.VENUE_PLACEMENTS_METRIC.value]
        self.depletions_metrics = [MenuColNames.SOLD_9LE_METRIC.value, MenuColNames.SOLD_CASES_METRIC.value]
        self.psudo_join_col = "join_col"
        self.depletions_agg_dict = {MenuColNames.SOLD_9LE_METRIC.value: np.sum, MenuColNames.SOLD_CASES_METRIC.value: np.sum}
        self.max_time_dimensions = [MenuColNames.MAX_TIME_MONTH_COL.value, MenuColNames.MAX_TIME_QUARTER_COL.value, MenuColNames.MAX_TIME_YEAR_COL.value]
        self.query_timing = 0
        self.query_count = 0

        self.removed_nones = False
        
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
            start_time = time.time()
            menu_df = pull_data(metrics=menu_metrics,
                                breakouts=breakouts,
                                filters=filters,
                                order_cols=order_cols,
                                query_row_limit=query_row_limit,
                                dataset_id=self.menu_dataset)
            end_time = time.time()
            exec_time = end_time - start_time
            print(f"total_rows: {len(menu_df)} with time: {exec_time:.2f}s")
            self.query_timing += np.round(exec_time, 2)
            self.query_count += 1

            dfs.append(menu_df)

        if depletion_metrics and not (cocktail_dims or cocktail_filter_dims):
            start_time = time.time()
            depletion_df = pull_data(metrics=depletion_metrics,
                                     breakouts=breakouts,
                                     filters=filters,
                                     order_cols=order_cols,
                                     query_row_limit=query_row_limit,
                                     dataset_id=self.depletion_dataset)
            end_time = time.time()
            exec_time = end_time - start_time
            print(f"total_rows: {len(depletion_df)} with time: {exec_time:.2f}s")
            self.query_timing += np.round(exec_time, 2)
            self.query_count += 1

            dfs.append(depletion_df)

        if is_cross_query:

            if sales_uplift_metrics:
                print(f"Filters: {filters}")
                filter_columns = [f["col"] for f in filters] if filters else []
                brand_or_supplier_present = any(col in filter_columns for col in [MenuColNames.BRAND_NAME_COL.value, MenuColNames.SUPPLIER_NAME_COL.value])
                
                if not brand_or_supplier_present:
                    raise exit_with_status(f"Either {MenuColNames.BRAND_NAME_COL.value} or {MenuColNames.SUPPLIER_NAME_COL.value} is required to calculate sales uplift. Please ask the user to provide one of the two.")

                if any(b in [MenuColNames.BRAND_NAME_COL.value, MenuColNames.SUPPLIER_NAME_COL.value] for b in breakouts):
                    raise exit_with_status(f"Brand and supplier breakouts are not supported for sales uplift. Please ask the user to remove one the filter")

                if len(sales_uplift_metrics) > 1:
                    raise exit_with_status(f"Only one sales uplift metric is supported at a time. Please ask the user to only select a single uplift metric at a time.")

                # Check if we have cocktail filters for an uplift other than cocktail uplift
                if sales_uplift_metrics[0].get("name") != MenuColNames.COCKTAIL_UPLIFT_METRIC.value and cocktail_filter_dims:
                    raise exit_with_status(f"{sales_uplift_metrics[0].get('name')} is not supported with cocktail filter dimensions. Did you mean to calculate Cocktail Uplift?")

                if sales_uplift_metrics and [f for f in filters if f["col"] == MenuColNames.VENUE_PREMISE_TYPE_COL.value]:
                    raise exit_with_status(f"Sales uplift is not supported filtering on {MenuColNames.VENUE_PREMISE_TYPE_COL.value}")


                uplift_metric_type = sales_uplift_metrics[0].get("name")

                venue_premise_filter = {"col": MenuColNames.VENUE_PREMISE_TYPE_COL.value, "op": PreQueryOperator.EQUALS.value, "val": "On-Premise"}
                product_id_filter = {"col": MenuColNames.PRODUCT_ID_COL.value, "op": PreQueryOperator.NOT_NULL.value, 'val': None}
                filters = [venue_premise_filter, product_id_filter] + filters if filters else [venue_premise_filter, product_id_filter]

                # Extract brand/supplier filters for later use
                brand_filters = [f for f in filters if f["col"] == MenuColNames.BRAND_NAME_COL.value]
                supplier_filters = [f for f in filters if f["col"] == MenuColNames.SUPPLIER_NAME_COL.value]
                
                # 1. Pull depletion data ONCE (remove cocktail filters)
                # depl_dims = [b for b in breakouts if b not in cocktail_dims and b not in time_period_dims]
                # uplift_common_dims = [MenuColNames.VENUE_ID_COL.value] + time_period_dims + depl_dims
                depl_filters = [f for f in filters if f["col"] not in self.cross_dims + [MenuColNames.PRODUCT_ID_COL.value]]
                
                start_time = time.time()
                depletions_df = pull_data(
                    metrics=[{"name": MenuColNames.SOLD_9LE_METRIC.value}],
                    breakouts=[MenuColNames.VENUE_ID_COL.value],
                    filters=depl_filters,
                    query_row_limit=10000000,
                    dataset_id=self.depletion_dataset
                )
                end_time = time.time()
                exec_time = end_time - start_time
                print(f"Depletion data - total_rows: {len(depletions_df)} with time: {exec_time:.2f}s")
                self.query_timing += np.round(exec_time, 2)
                self.query_count += 1
                
                # Aggregate depletion data by venue
                depl_agg = depletions_df.groupby(MenuColNames.VENUE_ID_COL.value).agg({
                    MenuColNames.SOLD_9LE_METRIC.value: 'sum'
                }).reset_index()
                
                # 2. Pull menu data WITH brand (for menu mention, single spirit, cocktail)
                start_time = time.time()
                menu_with_brand_df = pull_data(
                    metrics=[],
                    breakouts=[MenuColNames.VENUE_ID_COL.value, MenuColNames.PRODUCT_ID_COL.value, 
                            MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value],
                    filters=filters,
                    query_row_limit=10000000,
                    dataset_id=self.menu_dataset
                )
                end_time = time.time()
                exec_time = end_time - start_time
                print(f"Menu with brand - total_rows: {len(menu_with_brand_df)} with time: {exec_time:.2f}s")
                self.query_timing += np.round(exec_time, 2)
                self.query_count += 1
                
                # 3. Pull venues WITHOUT brand for just_in_distribution
                # Remove brand/supplier filters and add negated versions
                just_in_dist_filters = [f for f in filters if f["col"] not in [MenuColNames.BRAND_NAME_COL.value, MenuColNames.SUPPLIER_NAME_COL.value, MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value]]
                
                # Add negated brand/supplier filters
                for bf in brand_filters:
                    negated_brand_filter = bf.copy()
                    if type(bf.get("val")) == list:
                        negated_brand_filter["op"] = PreQueryOperator.NOT_IN.value
                    else:
                        negated_brand_filter["op"] = PreQueryOperator.NOT_EQUALS.value

                    just_in_dist_filters.append(negated_brand_filter)
                
                for sf in supplier_filters:
                    negated_supplier_filter = sf.copy()
                    if type(sf.get("val")) == list:
                        negated_supplier_filter["op"] = PreQueryOperator.NOT_IN.value
                    else:
                        negated_supplier_filter["op"] = PreQueryOperator.NOT_EQUALS.value
                    just_in_dist_filters.append(negated_supplier_filter)
                
                start_time = time.time()
                menu_without_brand_df = pull_data(
                    metrics=[],
                    breakouts=[MenuColNames.VENUE_ID_COL.value],
                    filters=just_in_dist_filters,
                    query_row_limit=10000000,
                    dataset_id=self.menu_dataset
                )
                end_time = time.time()
                exec_time = end_time - start_time
                print(f"Menu without brand - total_rows: {len(menu_without_brand_df)} with time: {exec_time:.2f}s")
                self.query_timing += np.round(exec_time, 2)
                self.query_count += 1
                
                # Calculate just_in_distribution (denominator - shared for all metrics)
                just_in_dist_venues = set(menu_without_brand_df[MenuColNames.VENUE_ID_COL.value].unique())
                
                def calculate_avg_depletion(venue_set, depl_agg):
                    venue_depl = depl_agg[depl_agg[MenuColNames.VENUE_ID_COL.value].isin(venue_set)]
                    count = len(venue_depl)
                    avg = venue_depl[MenuColNames.SOLD_9LE_METRIC.value].mean() if count > 0 else 0
                    return count, avg
                
                just_in_dist_count, just_in_dist_avg = calculate_avg_depletion(just_in_dist_venues, depl_agg)
                
                # Calculate metric-specific numerator
                match uplift_metric_type:
                    case MenuColNames.MENU_UPLIFT_METRIC.value:
                        # Menu mention venues (all venues with brand)
                        numerator_venues = set(menu_with_brand_df[MenuColNames.VENUE_ID_COL.value].unique())
                        numerator_count, numerator_avg = calculate_avg_depletion(numerator_venues, depl_agg)
                        
                    case MenuColNames.SINGLE_SPIRIT_UPLIFT_METRIC.value:
                        # Single spirit venues (venues with brand but NOT in cocktails)
                        single_spirit_df = menu_with_brand_df[menu_with_brand_df[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value] == "None"]
                        venues_with_cocktails = set(menu_with_brand_df[menu_with_brand_df[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value] != "None"][MenuColNames.VENUE_ID_COL.value].unique())
                        numerator_venues = set(single_spirit_df[MenuColNames.VENUE_ID_COL.value].unique()) - venues_with_cocktails
                        numerator_count, numerator_avg = calculate_avg_depletion(numerator_venues, depl_agg)
                        
                    case MenuColNames.COCKTAIL_UPLIFT_METRIC.value:
                        # Cocktail venues
                        cocktail_filter_exists = MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value in [f["col"] for f in filters]
                        if cocktail_filter_exists:
                            # Specific cocktail - use already filtered data
                            numerator_venues = set(menu_with_brand_df[menu_with_brand_df[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value] != "None"][MenuColNames.VENUE_ID_COL.value].unique())
                        else:
                            # Any cocktail
                            numerator_venues = set(menu_with_brand_df[menu_with_brand_df[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value] != "None"][MenuColNames.VENUE_ID_COL.value].unique())
                        numerator_count, numerator_avg = calculate_avg_depletion(numerator_venues, depl_agg)
                
                # Calculate uplift
                uplift_value = numerator_avg / just_in_dist_avg if just_in_dist_avg > 0 else 0
                
                # Get dimensions for structure
                time_period_dims = [d for d in breakouts if d in self.max_time_dimensions]
                depl_dims = [b for b in breakouts if b not in cocktail_dims and b not in time_period_dims]
                agg_dims = cocktail_dims + time_period_dims + depl_dims
                
                # Create base result with uplift value and dimensions
                result_data = {uplift_metric_type: uplift_value}
                
                # Add all dimensions to match structure
                for dim in agg_dims:
                    result_data[dim] = breakouts[breakouts.index(dim)]
                if "date_column" in breakouts:
                    result_data["date_column"] = breakouts[breakouts.index("date_column")]
                
                # Create the result dataframe
                result_df = pd.DataFrame([result_data])
                
                # If we have dimensions, aggregate to match structure
                if agg_dims:
                    result_df = result_df.groupby(agg_dims).agg({uplift_metric_type: np.mean}).reset_index()
                
                # Sort and limit if needed
                if query_row_limit:
                    result_df = result_df.sort_values(by=uplift_metric_type, ascending=False)
                    result_df = result_df.head(query_row_limit)
                
                dfs.append(result_df)

                # # get the total average sales uplift across the time period breakout
                # # time_period_dims = [d for d in depl_dims if d in self.max_time_dimensions]
                # sales_uplift_total_avg_agg_dict = {sales_uplift_metrics[0].get("name"): np.mean}

                # avg_join_dims = depl_dims + time_period_dims
                # if avg_join_dims:
                #     total_avg_sales_uplift_df = sales_uplift_df.groupby(avg_join_dims).agg(sales_uplift_total_avg_agg_dict).reset_index()
                # else:
                #     total_avg_sales_uplift_df = sales_uplift_df.agg(sales_uplift_total_avg_agg_dict).to_frame().T
                # total_avg_sales_uplift_df = total_avg_sales_uplift_df.rename(columns={sales_uplift_metrics[0].get("name"): "total_avg"})

                # # join the sales uplift df with the qualifier df on the common dims
                # sales_uplift_df = pd.merge(sales_uplift_df, venues_df, on=uplift_common_dims, how='inner')

                # # join the sales uplift df with the total avg sales uplift df on the time period dims and depletion dims
                # if avg_join_dims:
                #     sales_uplift_df = pd.merge(sales_uplift_df, total_avg_sales_uplift_df, on=avg_join_dims, how='left')
                # else:
                #     # total_avg_sales_uplift_df should be a scalar
                #     sales_uplift_df["total_avg"] = total_avg_sales_uplift_df.iloc[0]["total_avg"]

                # sales_uplift_joined_agg_dict = {sales_uplift_metrics[0].get("name"): np.mean, "total_avg": np.sum}
                # agg_dims = cocktail_dims + time_period_dims + depl_dims
                # if "date_column" in sales_uplift_df.columns and time_period_dims: 
                #     # keep the trend date_column, which will mirror the time_period dim used
                #     agg_dims.append("date_column")

                # if agg_dims:
                #     sales_uplift_df = sales_uplift_df.groupby(agg_dims).agg(sales_uplift_joined_agg_dict).reset_index()
                # else:
                #     sales_uplift_df = sales_uplift_df.agg(sales_uplift_joined_agg_dict).to_frame().T
                
                # # calculate the sales uplift
                # sales_uplift_df[MenuColNames.SALES_UPLIFT_METRIC.value] = sales_uplift_df[MenuColNames.SALES_UPLIFT_METRIC.value] / sales_uplift_df["total_avg"]

                # # drop the total_avg column
                # sales_uplift_df = sales_uplift_df.drop(columns=["total_avg"])
                # if query_row_limit:
                #     # sort by sales_uplift_metric in descending order
                #     sales_uplift_df = sales_uplift_df.sort_values(by=MenuColNames.SALES_UPLIFT_METRIC.value, ascending=False)
                #     sales_uplift_df = sales_uplift_df.head(query_row_limit)
                
                # dfs.append(sales_uplift_df)

            if (depletion_metrics and (cocktail_dims or cocktail_filter_dims)):

                qualifier_joining_dims = cocktail_dims + self.common_dims

                start_time = time.time()
                # limiting the data to only venues and product relevant for cocktails
                qualifier_df = pull_data(metrics=[],
                                        breakouts=qualifier_joining_dims,
                                        filters=filters,
                                        dataset_id=self.menu_dataset)
                end_time = time.time()
                exec_time = end_time - start_time
                print(f"total_rows: {len(qualifier_df)} with time: {exec_time:.2f}s")
                self.query_timing += np.round(exec_time, 2)
                self.query_count += 1

                qualifier_df = qualifier_df.drop_duplicates()

                # remove cocktail dims since it's not available on depletion data
                depl_dims = [b for b in breakouts if b not in cocktail_dims]
                depl_fils = [f for f in filters if f["col"] not in self.cross_dims] if filters else []

                start_time = time.time()
                pre_depletion_df = pull_data(metrics=depletion_metrics,
                                            breakouts=depl_dims + self.common_dims,
                                            filters=depl_fils,
                                            order_cols=order_cols,
                                            query_row_limit=query_row_limit,
                                            dataset_id=self.depletion_dataset)
                end_time = time.time()
                exec_time = end_time - start_time
                print(f"total_rows: {len(pre_depletion_df)} with time: {exec_time:.2f}s")
                self.query_timing += np.round(exec_time, 2)
                self.query_count += 1

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

        # check if any breakout columns have values equal to 'None' and remove the rows with None values
        none_value = "None"
        none_breakout_cols = [col for col in breakouts if df[col].isin([none_value]).any()]
        if none_breakout_cols:
            self.removed_nones = True
            df = df[~df[none_breakout_cols].isin([none_value]).all(axis=1)]

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

    def get_query_stats(self):
        df = pd.DataFrame({"Query Count": [self.query_count], "Query Timing (Incl. SQL Gen)": [self.query_timing]})
        print("--------- Query Stats ---------")
        print(df.to_string())
        return None