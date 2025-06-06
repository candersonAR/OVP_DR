from typing import Optional
from ar_analytics.helpers.utils import pull_data, exit_with_status, PreQueryOperator
from overproof_utilities import MenuColNames
import pandas as pd
import numpy as np
import time
import logging

_logger = logging.getLogger(__name__) # TODO: Use logger

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
            MenuColNames.PRODUCT_CATEGORY_NAME_COL.value,
            MenuColNames.CHAIN_NAME_COL.value,
            MenuColNames.VENUE_CATEGORY_COL.value,
            # MenuColNames.MENU_ITEM_NAME_COL.value, 
            # MenuColNames.MENU_ITEM_TYPE_COL.value
        ]
        # todo: sales uplift
        self.sales_uplift_metrics = [MenuColNames.COCKTAIL_UPLIFT_METRIC.value, MenuColNames.MENU_UPLIFT_METRIC.value, MenuColNames.SINGLE_SPIRIT_UPLIFT_METRIC.value]
        self.uplift_performance_metrics = [MenuColNames.UPLIFT_PERFORMANCE_MENU_MENTIONS_METRIC.value, MenuColNames.UPLIFT_PERFORMANCE_VPO_WITH_METRIC.value, MenuColNames.UPLIFT_PERFORMANCE_VPO_WITHOUT_METRIC.value]
        # joining dimensions (lowest common granularity) between menu and depletions data
        self.common_dims = [MenuColNames.VENUE_ID_COL.value, MenuColNames.PRODUCT_ID_COL.value]
        self.menu_metrics = [
            MenuColNames.MENU_PLACEMENTS_METRIC.value, 
            MenuColNames.VENUE_PLACEMENTS_METRIC.value,
            MenuColNames.STATE_MENTIONS_METRIC.value,
            MenuColNames.POSTAL_CODE_MENTIONS_METRIC.value
        ]
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
        uplift_performance_metrics = [m for m in metrics if m.get("name") in self.uplift_performance_metrics]

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
        is_uplift_performance_query = sales_uplift_metrics and uplift_performance_metrics

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
                # Defaults to sold 9le if no depletion metrics are provided
                default_9le_metric = [{'name': 'sold_9le', 'label': 'Sold 9le', 'sql': None, 'col': 'sold_9le', 'metric_type': None, 'is_share': None, 'fmt': ',.2f', 'growth_fmt': ',.2%', 'hide_percentage_change': False}]
                brand_or_supplier_present = any(col in filter_columns for col in [MenuColNames.BRAND_NAME_COL.value, MenuColNames.SUPPLIER_NAME_COL.value])

                if not brand_or_supplier_present:
                    raise exit_with_status(f"Either {MenuColNames.BRAND_NAME_COL.value} or {MenuColNames.SUPPLIER_NAME_COL.value} is required to calculate sales uplift. Please ask the user to provide one of the two.")

                if any(b in [MenuColNames.BRAND_NAME_COL.value, MenuColNames.SUPPLIER_NAME_COL.value] for b in breakouts):
                    raise exit_with_status(f"Brand and supplier breakouts are not supported for sales uplift. Please ask the user to remove one the breakouts")

                if len(sales_uplift_metrics) > 1:
                    raise exit_with_status(f"Only one sales uplift metric is supported at a time. Please ask the user to only select a single uplift metric at a time. The available metrics are: {', '.join(self.sales_uplift_metrics)}.")

                # Check if we have cocktail filters for an uplift other than cocktail uplift
                if sales_uplift_metrics[0].get("name") == MenuColNames.SINGLE_SPIRIT_UPLIFT_METRIC.value and cocktail_filter_dims:
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
                depl_dims = [b for b in breakouts if b not in cocktail_dims and b not in time_period_dims]
                uplift_common_dims = [MenuColNames.VENUE_ID_COL.value] + time_period_dims
                depl_filters = [f for f in filters if f["col"] not in self.cross_dims + [MenuColNames.PRODUCT_ID_COL.value]]
                
                start_time = time.time()
                depletions_df = pull_data(
                    metrics= default_9le_metric,
                    breakouts=uplift_common_dims + depl_dims,
                    filters=depl_filters,
                    query_row_limit=10000000,
                    dataset_id=self.depletion_dataset
                )
                end_time = time.time()
                exec_time = end_time - start_time
                print(f"Depletion data - total_rows: {len(depletions_df)} with time: {exec_time:.2f}s")
                self.query_timing += np.round(exec_time, 2)
                self.query_count += 1

                if depletions_df.empty:
                    raise exit_with_status(f"No depletion data found using the given filters: {depl_filters}. Please ask the user to provide a different combination of filters.")
                
                # Aggregate depletion data by venue
                depl_metric_names = [m.get("name") for m in default_9le_metric]
                depl_agg_dict = {k: v for k, v in self.depletions_agg_dict.items() if k in depl_metric_names}
                depl_agg = depletions_df.groupby(uplift_common_dims).agg(depl_agg_dict).reset_index()
                
                # 2. Pull menu data WITH brand (for menu mention, single spirit, cocktail)
                start_time = time.time()
                required_menu_dims = uplift_common_dims + cocktail_dims
                menu_with_brand_df = pull_data(
                    metrics=[],
                    breakouts= list(set([MenuColNames.PRODUCT_ID_COL.value, MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value] + required_menu_dims)),
                    filters=filters,
                    query_row_limit=10000000,
                    dataset_id=self.menu_dataset 
                )
                end_time = time.time()
                exec_time = end_time - start_time
                print(f"Menu with brand - total_rows: {len(menu_with_brand_df)} with time: {exec_time:.2f}s")
                self.query_timing += np.round(exec_time, 2)
                self.query_count += 1
                
                if menu_with_brand_df.empty:
                    raise exit_with_status(f"No menu data found for the specified brand using the given filters: {filters}. Please ask the user to provide a different combination of filters.")

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
                    breakouts=required_menu_dims,
                    filters=just_in_dist_filters,
                    query_row_limit=10000000,
                    dataset_id=self.menu_dataset
                )
                end_time = time.time()
                exec_time = end_time - start_time
                print(f"Menu without brand - total_rows: {len(menu_without_brand_df)} with time: {exec_time:.2f}s")
                self.query_timing += np.round(exec_time, 2)
                self.query_count += 1

                if menu_without_brand_df.empty:
                    raise exit_with_status(f"No menu data found for just in distribution using the given filters: {filters}. Please ask the user to provide a different combination of filters.")
            
                # Calculate uplift for each time period
                result_rows = []

                # Calculate just_in_distribution (denominator - shared for all metrics)
                def calculate_avg_depletion(venue_set, depl_agg, group_cols=None):
                    venue_depl = depl_agg[depl_agg[MenuColNames.VENUE_ID_COL.value].isin(venue_set)]
                    if group_cols:
                        # Group by dimensions if they exist
                        grouped = venue_depl.groupby(group_cols)[depl_metric_names].agg(['count', 'mean']).reset_index()
                        return grouped['sold_9le']['count'].tolist(), grouped['sold_9le']['mean'].tolist(), grouped[group_cols].values.tolist()
                    else:
                        count = len(venue_depl)
                        avg = venue_depl[depl_metric_names].mean() if count > 0 else [0]
                        return count, avg, None
                
                def create_row_data(time_periods, just_in_dist_avgs, numerator_avgs, numerator_counts, numerator_time_periods, dim_value=None):
                    # Just in dist time periods and numerator time periods may be different, so we need to only use the time periods that are present in both
                    if time_periods:
                        # Create dictionaries mapping time periods to their respective averages
                        just_in_dist_dict = {tuple(tp): avg for tp, avg in zip(time_periods, just_in_dist_avgs)}
                        numerator_dict = {tuple(tp): avg for tp, avg in zip(numerator_time_periods, numerator_avgs)}
                        
                        # Get union of time periods
                        all_time_periods = sorted(set(tuple(tp) for tp in time_periods) | set(tuple(tp) for tp in numerator_time_periods))
                        
                        # Calculate uplift for each time period
                        uplift_values = []
                        for tp in all_time_periods:
                            just_in_dist_avg = just_in_dist_dict.get(tp, 0)
                            numerator_avg = numerator_dict.get(tp, 0)
                            uplift = numerator_avg / just_in_dist_avg if just_in_dist_avg > 0 else 0
                            uplift_values.append((tp, uplift))
                        
                        for time_period, uplift_value in uplift_values:
                            row_data = {uplift_metric_type: uplift_value, time_period_dims[0]: time_period[0]}
                            
                            if dim_value is not None:
                                row_data[dimension] = dim_value
                            
                            row_data["date_column"] = time_period[0]
                            result_rows.append(row_data)
                    else:
                        # Calculate uplift without time periods
                        uplift_value = [numerator_avg / just_in_dist_avg if just_in_dist_avg > 0 else 0 for numerator_avg, just_in_dist_avg in zip(numerator_avgs, just_in_dist_avgs)]
                        if is_uplift_performance_query:
                            row_data = {MenuColNames.UPLIFT_PERFORMANCE_MENU_MENTIONS_METRIC.value: numerator_counts, MenuColNames.UPLIFT_PERFORMANCE_VPO_WITH_METRIC.value: numerator_avgs[0], MenuColNames.UPLIFT_PERFORMANCE_VPO_WITHOUT_METRIC.value: just_in_dist_avgs[0], uplift_metric_type: uplift_value[0]}
                        else:
                            row_data = {uplift_metric_type: uplift_value[0]}

                        if dim_value is not None:
                            row_data[dimension] = dim_value
                        
                        result_rows.append(row_data)

               
                # Get unique values for the single dimension if it exists
                dimension_values = []
                if len(cocktail_dims) == 1:
                    dimension = cocktail_dims[0]
                    dimension_values = menu_with_brand_df[dimension].unique().tolist()
                else:
                    dimension_values = []

                # If no dimension values are provided, calculate uplift without filtering venues by dimension value
                # just_in_dist_venues = set(menu_without_brand_df[MenuColNames.VENUE_ID_COL.value].unique())
                # just_in_dist_counts, just_in_dist_avgs, time_periods = calculate_avg_depletion(just_in_dist_venues, depl_agg, time_period_dims if time_period_dims else None)

                if not dimension_values:
                    just_in_dist_venues = set(menu_without_brand_df[MenuColNames.VENUE_ID_COL.value].unique())
                    just_in_dist_counts, just_in_dist_avgs, time_periods = calculate_avg_depletion(just_in_dist_venues, depl_agg, time_period_dims if time_period_dims else None)

                    # Calculate numerator for this dimension value
                    match uplift_metric_type:
                        case MenuColNames.MENU_UPLIFT_METRIC.value:
                            numerator_venues = set(menu_with_brand_df[MenuColNames.VENUE_ID_COL.value].unique())

                        case MenuColNames.SINGLE_SPIRIT_UPLIFT_METRIC.value:
                            single_spirit_df = menu_with_brand_df[menu_with_brand_df[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value] == "None"]
                            venues_with_cocktails = set(menu_with_brand_df[menu_with_brand_df[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value] != "None"][MenuColNames.VENUE_ID_COL.value].unique())
                            numerator_venues = set(single_spirit_df[MenuColNames.VENUE_ID_COL.value].unique()) - venues_with_cocktails
                        
                        case MenuColNames.COCKTAIL_UPLIFT_METRIC.value:
                            numerator_venues = set(menu_with_brand_df[menu_with_brand_df[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value] != "None"][MenuColNames.VENUE_ID_COL.value].unique())
                    
                    # Calculate numerator average for this dimension value
                    numerator_counts, numerator_avgs, numerator_time_periods = calculate_avg_depletion(numerator_venues, depl_agg, time_period_dims if time_period_dims else None)
                    
                    create_row_data(time_periods, just_in_dist_avgs, numerator_avgs, numerator_counts, numerator_time_periods, dim_value=None)

                # If dimension values are provided, calculate uplift for each dimension value separately
                else:
                    for dim_value in dimension_values: 
                        breakout_menu_with_brand_df = menu_with_brand_df[menu_with_brand_df[dimension] == dim_value]
                        breakout_menu_without_brand_df = menu_without_brand_df[menu_without_brand_df[dimension] == dim_value]

                        just_in_dist_venues = set(breakout_menu_without_brand_df[MenuColNames.VENUE_ID_COL.value].unique())
                        just_in_dist_counts, just_in_dist_avgs, time_periods = calculate_avg_depletion(just_in_dist_venues, depl_agg, time_period_dims if time_period_dims else None)

                        
                        # Calculate numerator for this dimension value
                        match uplift_metric_type:
                            case MenuColNames.MENU_UPLIFT_METRIC.value:
                                numerator_venues = set(breakout_menu_with_brand_df[MenuColNames.VENUE_ID_COL.value].unique())
                            case MenuColNames.SINGLE_SPIRIT_UPLIFT_METRIC.value:
                                single_spirit_df = breakout_menu_with_brand_df[breakout_menu_with_brand_df[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value] == "None"]
                                venues_with_cocktails = set(breakout_menu_with_brand_df[breakout_menu_with_brand_df[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value] != "None"][MenuColNames.VENUE_ID_COL.value].unique())
                                numerator_venues = set(single_spirit_df[MenuColNames.VENUE_ID_COL.value].unique()) - venues_with_cocktails
                            case MenuColNames.COCKTAIL_UPLIFT_METRIC.value:
                                numerator_venues = set(breakout_menu_with_brand_df[breakout_menu_with_brand_df[MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value] != "None"][MenuColNames.VENUE_ID_COL.value].unique())
                                
                        # Calculate numerator average for this dimension value
                        numerator_counts, numerator_avgs, numerator_time_periods = calculate_avg_depletion(numerator_venues, depl_agg, time_period_dims if time_period_dims else None)
                        
                        create_row_data(time_periods, just_in_dist_avgs, numerator_avgs, numerator_counts, numerator_time_periods, dim_value=dim_value)
                    
                   
                    # Add other dimensions
                    # for dim in depl_dims:
                    #     if dim in breakouts:
                    #         row_data[dim] = breakouts[breakouts.index(dim)]
                    
                    
                    # result_rows.append(row_data)
                
                # Create the result dataframe
                result_df = pd.DataFrame(result_rows)
                
                # Sort and limit if needed
                sort_metric = uplift_metric_type if not is_uplift_performance_query else MenuColNames.UPLIFT_PERFORMANCE_MENU_MENTIONS_METRIC.value
                result_df = result_df.sort_values(by=sort_metric, ascending=False)

                if query_row_limit:
                    result_df = result_df.head(query_row_limit)
                
                dfs.append(result_df)

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
