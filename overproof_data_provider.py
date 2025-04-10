from ar_analytics.helpers.utils import pull_data
import pandas as pd
import numpy as np

class DataProvider(object):
    def __init__(self):
        # make sure this is correct
        self.menu_dataset = "c50c3d81-682f-463e-a924-747d62e62318" # Ar Max Menu Table
        self.depletion_dataset = "d91a492a-d62a-405e-90d8-0b9a3984f5ea" # Ar Max Depletions

        self.cross_dims = ["cocktail__name", "cocktail__style", "cocktail_family", "cocktail_group", "cocktail__flavors", "cocktail__derived_from", "menu_item__item_name", "menu_item__item_type"]
        # todo: sales uplift
        self.cross_metrics = ["sales_uplift"]
        # joining dimensions (lowest common granularity) between menu and depletions data
        self.common_dims = ["venue_id", "product_id"]
        self.menu_metrics = ["menu_placements", "venue_placements"]
        self.depletions_metrics = ["sold_9le", "sold_cases"]
        self.psudo_join_col = "join_col"
        self.depletions_agg_dict = {"sold_9le": np.sum, "sold_cases": np.sum}

    def pull_data(self,
                  metrics,
                  breakouts=None,
                  filters=None,
                  order_cols=None,
                  query_row_limit=None):

        df = pd.DataFrame()
        # todo: handle order cols, only used in trend to determine top n

        breakouts = breakouts or []

        menu_metrics = [m for m in metrics if m.get("name") in self.menu_metrics]
        depletion_metrics = [m for m in metrics if m.get("name") in self.depletions_metrics]
        cocktail_metrics = [m for m in metrics if m.get("name") in self.cross_metrics]

        if filters:
            cocktail_filter_dims = [f["col"] for f in filters if f["col"] in self.cross_dims]
        else:
            cocktail_filter_dims = []

        if breakouts:
            cocktail_dims = [b for b in breakouts if b in self.cross_dims]
        else:
            cocktail_dims = []

        is_cross_query = cocktail_metrics or (depletion_metrics and (cocktail_dims or cocktail_filter_dims))

        dfs = []
        if menu_metrics:
            menu_df = pull_data(metrics=menu_metrics,
                                breakouts=breakouts,
                                filters=filters,
                                order_cols=order_cols,
                                query_row_limit=query_row_limit,
                                dataset_id=self.menu_dataset)
            dfs.append(menu_df)

        if depletion_metrics and not is_cross_query:
            depletion_df = pull_data(metrics=depletion_metrics,
                                     breakouts=breakouts,
                                     filters=filters,
                                     order_cols=order_cols,
                                     query_row_limit=query_row_limit,
                                     dataset_id=self.depletion_dataset)
            dfs.append(depletion_df)

        if is_cross_query:
            joining_dims = cocktail_dims + self.common_dims

            # limiting the data to only venues and product relevant for cocktails
            qualifier_df = pull_data(metrics=[],
                                     breakouts=joining_dims,
                                     filters=filters,
                                     dataset_id=self.menu_dataset)

            qualifier_df = qualifier_df.drop_duplicates()

            # remove cocktail dims since it's not available on depletion data
            depl_dims = [b for b in breakouts if b not in cocktail_dims]
            depl_fils = [f for f in filters if f["col"] not in self.cross_dims]
            pre_depletion_df = pull_data(metrics=depletion_metrics,
                                         breakouts=depl_dims + self.common_dims,
                                         filters=depl_fils,
                                         order_cols=order_cols,
                                         query_row_limit=query_row_limit,
                                         dataset_id=self.depletion_dataset)

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
    