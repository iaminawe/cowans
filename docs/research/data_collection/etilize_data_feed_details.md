# Etilize Data Feed Details

This document describes the structure and content of the Etilize data feed used for product information.

## Column Headers and Data Types

The Etilize CSV data feed includes the following columns (as seen in `data/CWS_Etilize_shopify.csv`):

*   Handle
*   Title
*   URL handle
*   Description
*   Vendor
*   Type
*   Tags
*   Published
*   Status
*   SKU
*   Barcode
*   Option1 Name
*   Option1 Value
*   Charge tax
*   Continue selling when out of stock
*   Weight value (grams)
*   Weight unit for display
*   Requires shipping
*   Fulfillment service
*   Product image URL
*   Image position
*   Image alt text
*   Gift Card
*   SEO Title
*   SEO Description
*   Google Shopping / Google Product Category
*   Google Shopping / Gender
*   Google Shopping / Age Group
*   Google Shopping / MPN
*   Google Shopping / AdWords Grouping
*   Google Shopping / AdWords Labels
*   Google Shopping / Condition
*   Google Shopping / Custom Product
*   Google Shopping / Custom Label 0
*   Google Shopping / Custom Label 1
*   Google Shopping / Custom Label 2
*   Google Shopping / Custom Label 3
*   Google Shopping / Custom Label 4
*   metafield_json

## Column Removal

The script `scripts/remove_empty_columns.py` removes any columns that are completely empty from the original Etilize CSV file (`CWS_Etilize.csv`) before the metafield consolidation occurs. A list of removed columns is saved in `removed_columns.txt`. This helps reduce the size of the data and improve processing efficiency by removing unnecessary data.

## Consolidated Metafield (metafield_json)

The program consolidates multiple columns from the Etilize CSV into a single JSON formatted metafield called `metafield_json`. The program identifies columns that begin with the prefix `Metafield: custom.`. The script `scripts/data_processing/create_metafields.py` handles the creation of this field.

The script removes the following parts of the column header to get the key name for the JSON object:

*   `Metafield: custom.` prefix
*   `[list.single_line_text]` suffix

Nested keys are supported using periods, for example, a column named `Metafield: custom.product_details.features` would become a nested JSON structure:

```json
{
  "metafield": {
    "namespace": "custom",
    "key": "product_info",
    "type": "json",
    "value": {
      "product_details": {
        "features": "the value from the column"
      }
    }
  }
}
```

## Known Inconsistencies and Quirks

Based on initial analysis, these are known aspects to consider:

*   The source CSV utilizes a large number of columns for product metadata, many of which are specific to product types and may be empty for a given product.
*   The column names for product metadata follow a specific structure: `Metafield: custom.[field name][list.single_line_text]`
*   Some data might be missing or inconsistent within the 'Metafield: custom.' prefixed columns, requiring data validation and cleaning steps prior to the creation of the JSON object.
*   The `remove_empty_columns.py` script is used to reduce the data set size by removing columns that are completely empty.
*   The script `scripts/data_processing/create_metafields.py` handles the creation of the metafield and its transformation logic, creating a JSON object with the namespace "custom" and key "product_info".