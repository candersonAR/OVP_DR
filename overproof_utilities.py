import copy
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
    SALES_UPLIFT_METRIC = "sales_uplift"

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

    VENUE_ID_COL = "venue_id"
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

    helper = SharedFn()

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