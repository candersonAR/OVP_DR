from enum import Enum
from typing import List, Tuple

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
    COCKTAIL_GROUP_COL = "cocktail__group"
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

def map_cocktail_breakouts(breakouts: List[str]) -> List[str]:
    return [cocktail_to_ingredient_of_cocktail[b.lower()] if b.lower() in cocktail_to_ingredient_of_cocktail else b for b in breakouts]

def map_cocktail_filters(filters: list[dict]) -> list[dict]:
    return [
        {
            "col": cocktail_to_ingredient_of_cocktail[f["col"].lower()], 
            "op": f["op"], 
            "val": f["val"]
        } 
        if f["col"].lower() in cocktail_to_ingredient_of_cocktail else f 
        for f in filters
    ]

def map_cocktail_filters_and_breakouts(filters: list[dict], breakouts: list[str]) -> Tuple[List[dict], List[str]]:
    """
    Maps the cocktail breakouts/filters to the ingredient of cocktail breakouts/filters when there are product dimensions.
    Product dimensions only are applicable for ingredients of cocktails.

    Args:
        filters: list[dict]: The filters to be mapped.
        breakouts: list[str]: The breakouts to be mapped.

    Returns:
        Tuple[List[dict], List[str]]: The mapped filters and breakouts.
    """

    if has_product_dimension(filters, breakouts):
        return map_cocktail_filters(filters), map_cocktail_breakouts(breakouts)
    else:
        return filters, breakouts
