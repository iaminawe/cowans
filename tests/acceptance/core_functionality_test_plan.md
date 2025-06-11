# Core Integration System Test Plan

## Overview

This test plan defines the testing strategy for the Core Integration System, focusing on FTP downloader, data transformer, and Shopify uploader components. The plan adopts London School TDD principles, emphasizing interaction-based testing and verification of observable outcomes through mocked collaborators.

## Test Scope

This plan verifies the following AI Verifiable End Results from PRDMasterPlan.md:
- Successful automated FTP downloads from Etilize
- Correct transformation of product data with JSON metafields
- Successful batch uploads to Shopify
- Completion of core automated tests

## Test Strategy

### London School TDD Approach
- Focus on behavior verification through component interactions
- Mock external collaborators (FTP server, Shopify API)
- Verify observable outcomes rather than internal state
- Test components in isolation with clear interfaces

### Recursive Testing Strategy

#### Test Categories and Tags
- `@quick`: Basic function tests (run on every code change)
- `@integration`: Component interaction tests (run before merge)
- `@e2e`: End-to-end flow tests (run nightly)
- `@performance`: Load and stress tests (run weekly)

#### SDLC Trigger Points
1. Code Changes
   - Run: Quick tests for modified components
   - Verify: Basic functionality remains intact

2. Pull Request
   - Run: Integration tests for affected modules
   - Verify: Component interactions work correctly

3. Nightly Build
   - Run: All E2E tests
   - Verify: Complete system flow

4. Weekly Schedule
   - Run: Performance and stress tests
   - Verify: System handles expected load

## Test Cases

### 1. FTP Downloader Module

#### 1.1 FTP Connection Test
**AI Verifiable End Result:** Successful FTP connection and authentication
- **Unit:** FTPDownloader class
- **Collaborators to Mock:**
  - ftplib.FTP (mock FTP server responses)
  - LoggingService (verify logging calls)
- **Interactions to Test:**
  - connect() method calls FTP with correct credentials
  - Error handling for connection failures
- **Observable Outcomes:**
  - Successful connection establishment
  - Correct error propagation
- **Test Scope:** @quick

#### 1.2 File Download Test
**AI Verifiable End Result:** Successful file download verification
- **Unit:** FTPDownloader download_file method
- **Collaborators to Mock:**
  - ftplib.FTP (mock file retrieval)
  - FileSystem (mock file writing)
- **Interactions to Test:**
  - RETR command execution
  - Local file writing
- **Observable Outcomes:**
  - File downloaded to correct location
  - Correct handling of transfer errors
- **Test Scope:** @integration

### 2. Data Transformer Module

#### 2.1 CSV Processing Test
**AI Verifiable End Result:** Correct CSV data parsing
- **Unit:** DataTransformer parse_csv method
- **Collaborators to Mock:**
  - CSV Reader
  - LoggingService
- **Interactions to Test:**
  - CSV file reading
  - Data validation
- **Observable Outcomes:**
  - Correct data structure creation
  - Proper handling of malformed data
- **Test Scope:** @quick

#### 2.2 JSON Metafield Creation Test
**AI Verifiable End Result:** Correct JSON metafield generation
- **Unit:** DataTransformer create_metafields method
- **Collaborators to Mock:**
  - MetafieldValidator
- **Interactions to Test:**
  - Metafield creation logic
  - Validation calls
- **Observable Outcomes:**
  - Valid JSON metafield structure
  - Correct error handling for invalid data
- **Test Scope:** @quick

### 3. Shopify Uploader Module

#### 3.1 API Authentication Test
**AI Verifiable End Result:** Successful Shopify API authentication
- **Unit:** ShopifyUploader class
- **Collaborators to Mock:**
  - shopify-api-js client
  - LoggingService
- **Interactions to Test:**
  - API client initialization
  - Authentication flow
- **Observable Outcomes:**
  - Successful API client setup
  - Proper error handling
- **Test Scope:** @quick

#### 3.2 Product Upload Test
**AI Verifiable End Result:** Successful batch product upload
- **Unit:** ShopifyUploader upload_products method
- **Collaborators to Mock:**
  - Shopify API client
  - RateLimiter
- **Interactions to Test:**
  - Batch upload requests
  - Rate limit handling
- **Observable Outcomes:**
  - Successful product creation/update
  - Proper handling of API errors
- **Test Scope:** @integration

### 4. End-to-End Integration Tests

#### 4.1 Complete Sync Flow Test
**AI Verifiable End Result:** Successful end-to-end sync process
- **Scope:** Full system integration
- **Components Involved:**
  - FTP Downloader
  - Data Transformer
  - Shopify Uploader
- **Test Flow:**
  1. Trigger sync process
  2. Verify FTP download
  3. Check data transformation
  4. Confirm Shopify upload
- **Observable Outcomes:**
  - Complete sync success
  - Correct error handling and recovery
- **Test Scope:** @e2e

## Test Data Requirements

### Mock Data Sets
1. Small Catalog (100 products)
   - Location: test_data/small_catalog.csv
   - Use: Quick tests and basic validation

2. Medium Catalog (1000 products)
   - Location: test_data/medium_catalog.csv
   - Use: Integration tests and performance validation

3. Large Catalog (10,000 products)
   - Location: test_data/large_catalog.csv
   - Use: Load testing and stress testing

### Expected Results
1. Metafield Structure
   - Location: test_data/expected_metafields.json
   - Use: Verify transformation output

2. Product Structure
   - Location: test_data/expected_product_structure.json
   - Use: Verify Shopify upload format

## Mock Configurations

### FTP Server Mock
```python
class MockFTPServer:
    def mockSuccessfulConnection():
        return {'host': 'test-ftp.etilize.com', 'status': 200}
    
    def mockFileList():
        return ['product_feed.csv', 'metadata.txt']
```

### Shopify API Mock
```python
class MockShopifyAPI:
    def mockSuccessfulAuth():
        return {'access_token': 'test_token', 'status': 'authorized'}
    
    def mockProductCreation():
        return {'product_id': '123', 'status': 'created'}
```

## Test Implementation Notes

1. Test Independence
   - Each test must run in isolation
   - Use fresh mock instances for each test
   - Clean up test data after execution

2. Error Simulation
   - Test network failures
   - Test invalid data scenarios
   - Test API rate limiting

3. Performance Metrics
   - Track execution time
   - Monitor memory usage
   - Verify batch processing efficiency

## AI Verifiable Success Criteria

1. Test Coverage
   - Minimum 80% code coverage
   - All critical paths tested
   - All error scenarios covered

2. Performance Targets
   - Download completion < 5 minutes
   - Transformation < 2 minutes per 1000 products
   - Upload < 10 minutes per 1000 products

3. Integration Success
   - Clean test runs in CI pipeline
   - No regressions in existing functionality
   - All AI Verifiable End Results achieved