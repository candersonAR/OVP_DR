import copy
import math
import pandas as pd

from enum import Enum
from typing import List, Tuple
from ar_analytics.helpers.utils import SharedFn

# Cocktail dimension constants

class MenuColNames(Enum):
    # Metric names
    MENU_PLACEMENTS_METRIC = "menu_placements"
    VENUE_PLACEMENTS_METRIC = "venue_placements"
    MENU_PLACEMENTS_SHARE_METRIC = "menu_placements_share"
    SOLD_9LE_METRIC = "sold_9le"
    SOLD_CASES_METRIC = "sold_cases"
    STATE_MENTIONS_METRIC = "state_mentions"
    POSTAL_CODE_MENTIONS_METRIC = "postal_code_mentions"

    MENU_UPLIFT_METRIC = "menu_uplift"
    SINGLE_SPIRIT_UPLIFT_METRIC = "single_spirit_uplift"
    COCKTAIL_UPLIFT_METRIC = "cocktail_uplift"

    UPLIFT_PERFORMANCE_MENU_MENTIONS_METRIC = "menu_mentions"
    UPLIFT_PERFORMANCE_VPO_WITH_METRIC = "vpo_with"
    UPLIFT_PERFORMANCE_VPO_WITHOUT_METRIC = "vpo_without"

    # Dimension names
    COCKTAIL_NAME_COL = "cocktail__name"
    COCKTAIL_GROUP_COL = "cocktail_group"
    COCKTAIL_STYLE_COL = "cocktail__style"
    COCKTAIL_FAMILY_COL = "cocktail_family"
    COCKTAIL_FLAVORS_COL = "cocktail__flavors"
    COCKTAIL_DERIVED_FROM_COL = "cocktail__derived_from"

    INGREDIENT_OF_COCKTAIL_NAME_COL = "ingredient_of_cocktail_name"
    INGREDIENT_OF_COCKTAIL_GROUP_COL = "ingredient_of_cocktail_group"
    INGREDIENT_OF_COCKTAIL_STYLE_COL = "ingredient_of_cocktail_style"
    INGREDIENT_OF_COCKTAIL_FAMILY_COL = "ingredient_of_cocktail_family"

    MENU_ITEM_NAME_COL = "menu_item_name"
    MENU_ITEM_TYPE_COL = "menu_item_type"

    PRODUCT_NAME_COL = "product__name"
    BRAND_NAME_COL = "brand_name"
    PRODUCT_TYPE_NAME_COL = "product_type_name"
    PRODUCT_CATEGORY_NAME_COL = "product_category_name"
    PRODUCT_CATEGORY_FAMILY_NAME_COL = "product_category_family_name"
    PRODUCT_SUBCATEGORY_NAME_COL = "product_subcategory_name"
    SUPPLIER_NAME_COL = "supplier_name"

    COUNTRY_CODE_COL = "country_code"

    VENUE_ID_COL = "venue_id"
    VENUE_NAME_COL = "venue__name"
    VENUE_CATEGORY_COL = "venue__category_name"
    VENUE_PREMISE_TYPE_COL = "venue__premise_type"
    CHAIN_NAME_COL = "chain_name"
    PRODUCT_ID_COL = "product_id"

    MAX_TIME_DATE_COL = "max_time_date"
    MAX_TIME_MONTH_COL = "max_time_month"
    MAX_TIME_QUARTER_COL = "max_time_quarter"
    MAX_TIME_YEAR_COL = "max_time_year"

cocktail_to_ingredient_of_cocktail = {
    MenuColNames.COCKTAIL_NAME_COL.value: MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value,
    MenuColNames.COCKTAIL_GROUP_COL.value: MenuColNames.INGREDIENT_OF_COCKTAIL_GROUP_COL.value,
    MenuColNames.COCKTAIL_STYLE_COL.value: MenuColNames.INGREDIENT_OF_COCKTAIL_STYLE_COL.value,
    MenuColNames.COCKTAIL_FAMILY_COL.value: MenuColNames.INGREDIENT_OF_COCKTAIL_FAMILY_COL.value,
}

ingredient_of_cocktail_to_cocktail = {v: k for k, v in cocktail_to_ingredient_of_cocktail.items()}

product_dimensions = [
    MenuColNames.PRODUCT_NAME_COL.value, 
    MenuColNames.BRAND_NAME_COL.value, 
    MenuColNames.PRODUCT_TYPE_NAME_COL.value, 
    MenuColNames.PRODUCT_CATEGORY_NAME_COL.value, 
    MenuColNames.PRODUCT_CATEGORY_FAMILY_NAME_COL.value, 
    MenuColNames.PRODUCT_SUBCATEGORY_NAME_COL.value, 
    MenuColNames.SUPPLIER_NAME_COL.value
]

def has_product_dimension(filters: List[dict] = None, breakouts: List[str] = None) -> bool:
    
    if filters is None:
        filters = []
    if breakouts is None:
        breakouts = []

    return any(f["col"].lower() in product_dimensions for f in filters) or any(b.lower() in product_dimensions for b in breakouts)

def map_breakouts(breakouts: List[str], mapping_dict: dict) -> List[str]:
    return [mapping_dict[b.lower()] if b.lower() in mapping_dict else b for b in breakouts]

def map_filters(filters: list[dict], mapping_dict: dict) -> list[dict]:
    return [
        {
            "col": mapping_dict[f["col"].lower()], 
            "op": f["op"], 
            "val": f["val"]
        } 
        if f["col"].lower() in mapping_dict else f 
        for f in filters
    ]

def map_cocktails(filters: list[dict], breakouts: list[str], dim_hierarchy: List[dict], dim_props: dict) -> Tuple[List[dict], List[str], List[dict]]:
    """
    Maps the cocktail breakouts/filters to the ingredient of cocktail breakouts/filters when there are product dimensions.
    Product dimensions only are applicable for ingredients of cocktails.

    Args:
        filters: list[dict]: The filters to be mapped.
        breakouts: list[str]: The breakouts to be mapped.

    Returns:
        Tuple[List[dict], List[str]]: The mapped filters and breakouts.
    """

    dim_hierarchy = map_dimension_hierarchy(filters, breakouts, dim_hierarchy, dim_props)
    mapping_dict = cocktail_to_ingredient_of_cocktail if has_product_dimension(filters, breakouts) else ingredient_of_cocktail_to_cocktail

    return map_filters(filters, mapping_dict), map_breakouts(breakouts, mapping_dict), dim_hierarchy
    
def map_dimension_hierarchy(filters: list[dict], breakouts: list[str], dim_hierarchy: List[dict], dim_props: dict) -> dict:
    """
    Maps the cocktail dimension hierarchy to the ingredient of cocktail dimension hierarchy when there are product dimensions.
    Product dimensions only are applicable for ingredients of cocktails.
    """

    helper = OverproofSharedFn()

    hpd = has_product_dimension(filters, breakouts)

    if hpd:
        mapping_dict = cocktail_to_ingredient_of_cocktail
    else:
        mapping_dict = ingredient_of_cocktail_to_cocktail

    def map_dimension(nodes: List[dict]) -> List[dict]:

        new_nodes = []

        for node in nodes:
            new_node = copy.deepcopy(node)

            if not hpd and new_node["col"].lower() in product_dimensions:
                continue

            if new_node["col"].lower() in mapping_dict:
                updated_dim = helper.get_dimension_prop(mapping_dict[new_node["col"].lower()], dim_props)
                new_node["name"] = updated_dim.get("label", updated_dim["name"])
                new_node["col"] = updated_dim["name"]

            if node["children"]:
                new_node["children"] = map_dimension(node["children"])

            new_nodes.append(new_node)

        return new_nodes        

    return map_dimension(dim_hierarchy)

def map_msa_views(filters: list[dict], views=List[dict]) -> List[dict]:

    # Check if any of the filters are product dimensions
    hpd = has_product_dimension(filters=filters)

    if hpd:
        mapping_dict = cocktail_to_ingredient_of_cocktail
    else:
        mapping_dict = ingredient_of_cocktail_to_cocktail

    def apply_mapping(view: dict) -> dict:
        if view["dim"].lower() in mapping_dict:
            view["dim"] = mapping_dict[view["dim"].lower()]
        return view
    
    updated_view = []

    for obj in views:
        new_obj = apply_mapping(obj)
        if "drilldown" in new_obj and new_obj["drilldown"]:
            new_obj["drilldown"] = apply_mapping(new_obj["drilldown"])
        updated_view.append(new_obj)

    return updated_view

class OverproofSharedFn(SharedFn):

    def __init__(self, ds_meta={}):
        super().__init__(ds_meta)
    
    # Overwritten get_formatted_num to handle the 'x' suffix, ie ',.2x'
    def get_formatted_num(self, num: float | int | str, met_format: str, pretty_num=False, signed=False):

        def pretty_num_format(n: int | float, fmt: str):
            if math.isinf(n):
                return "Infinity"
            if math.isnan(n):
                return "NaN"

            if '$' in fmt:
                return '$' + make_pretty_num(n)
            if '%' in fmt:
                return '{}%'.format(make_pretty_num(n * 100))

            return make_pretty_num(n)

        def make_pretty_num(n: int | float, is_int=False):
            n = float(n)

            if -10 < n < 10:
                new_num = round(n, 2)
                if is_int:
                    new_num = int(new_num)
                return str(new_num)

            elif -100 < n < 100:
                new_num = round(n, 2)
                if is_int:
                    new_num = int(new_num)
                return str(new_num)

            mill_names = ['', 'K', 'M', 'B', 'T']
            mill_idx = max(0, min(len(mill_names) - 1, int(math.floor(0 if n == 0 else math.log10(abs(n)) / 3))))

            return '{:.1f}{}'.format(n / 10 ** (3 * mill_idx), mill_names[mill_idx])

        # convert to float if string, else return as is
        if isinstance(num, str):
            try:
                num = float(num)
            except:
                return num

        if not met_format:
            met_format = ",.2f"

        if "," in met_format:
            prefix, met_format = met_format.split(",")
            met_format = "," + met_format
        else:
            prefix = ""

        if num < 0:
            sign = "-"
        elif signed and num > 0:
            sign = "+"
        else:
            sign = ""

        suffix = ""
        if "bps" in met_format:
            met_format = met_format.replace("bps", "f").replace(",", "").strip(' ') or ".0f"
            suffix = " bps"
            num = num * 100 * 100
            pretty_num = False
        if "pp" in met_format:
            met_format = met_format.replace("pp", "f").replace(",", "").strip(' ') or ".2f"
            suffix = " pp"
            num = num * 100
            pretty_num = False

        ## Overwrite the default behavior to handle the 'x' suffix, ie ',.2x'
        if 'x' in met_format:
            met_format = met_format.replace('x', 'f').replace(',', '').strip(' ') or ".2f"
            suffix = "x"
            pretty_num = False
        ##

        if not pretty_num:
            fmt_num = f"{sign}{prefix}{abs(num):{met_format}}{suffix}"
        else:
            fmt_num = f"{sign}{prefix}{pretty_num_format(abs(num), met_format)}{suffix}"

        return fmt_num
    

def check_count_metric(metric: dict) -> bool:
    met_name = metric.get('name')
    count_metrics = [MenuColNames.MENU_PLACEMENTS_METRIC.value, MenuColNames.VENUE_PLACEMENTS_METRIC.value]
    return met_name in count_metrics

def calculate_market_share_denominator(
        pull_data_func,
        metrics,
        breakouts=[],
        filters=[],
        order_cols=None,
        query_row_limit=None,
        subject_breakout=None
) -> pd.DataFrame:
    '''
    Calculate the denominator for the market share calculation.
    Provides the normal denominator for non-count metrics.
    Provides the sum of count metrics for the subject breakout as the denominator for count metrics.
    '''

    if subject_breakout:
        non_count_metrics = [m for m in metrics if not check_count_metric(m)]
        count_metrics = [m for m in metrics if check_count_metric(m)]
    else:
        non_count_metrics = metrics
        count_metrics = []

    non_count_df = pd.DataFrame()
    count_df = pd.DataFrame()

    if non_count_metrics:
        non_count_df = pull_data_func(non_count_metrics, breakouts, filters, order_cols, query_row_limit)

    if count_metrics:
        # groupby dims + subject_breakout, then sum over everything except the subject_breakout
        count_df = pull_data_func(count_metrics, breakouts + [subject_breakout], filters, order_cols,
                                        query_row_limit)
        if breakouts:
            count_df = count_df.groupby(breakouts).sum().reset_index()
        else:
            count_df = count_df.groupby(lambda x: True).sum().reset_index(drop=True)

    if not non_count_df.empty and not count_df.empty:
        df = pd.merge(non_count_df, count_df, on=breakouts, how='inner')
    elif non_count_df.empty and not count_df.empty:
        df = count_df
    elif not non_count_df.empty and count_df.empty:
        df = non_count_df
    else:
        df = pd.DataFrame()

    return df