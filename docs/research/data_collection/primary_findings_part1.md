# Primary Findings: Etilize CSV Data Structure and Shopify API Integration

This document summarizes the primary findings from the AI search regarding Etilize CSV data structure and Shopify API integration best practices.

*   **Etilize CSV Data Structure:** Etilize provides product data in CSV format. A sample file, `data/CWS_Etilize.csv`, is available. Common column headers include ProductID, SKU, Title, Description, Price, Category, Manufacturer and ImageURL. Ensure that the data types in CSV match the expected data types in Shopify. Special characters in text fields should be properly escaped.
*   **Data Transformation Scripts:** The `scripts` directory contains scripts for data transformation. `remove_empty_columns.py` removes empty columns from the CSV, and `create_metafields.py` consolidates multiple specification columns into a single JSON metafield for Shopify.
*   **Shopify API Integration:** Use OAuth 2.0 for secure access to Shopify Admin API. Handle rate limits with exponential backoff retries. For large catalogs, use Shopify's bulkOperations GraphQL API for efficient data import.
*   **Data Mapping:** Map Etilize CSV columns to Shopify product API fields (e.g., SKU to variants.sku, ProductName to product.title, Price to variants.price, Inventory to inventory_levels.available).
*   **Error Handling:** Validate CSV data before import. Log errors with row numbers and failed fields for debugging.
*   **Inventory Synchronization:** Use inventoryLevels endpoints to update stock levels in real time.
*   **Optimization Strategies:** Consider using webhooks to trigger CSV processing when Etilize data updates, caching frequently accessed data, and implementing delta updates.

These findings provide a foundation for understanding the key aspects of integrating Etilize CSV data with the Shopify API. Further research will be conducted to address specific knowledge gaps and refine these findings.