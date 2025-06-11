# **Product Feed Integration System – Development Plan & Requirements**

## **Project Overview & Objectives**

This project aims to build a robust pipeline that automates the integration of product data from Etilize (a product information feed via FTP) into Shopify. The system will fetch and combine data, produce a merged product dataset (including a consolidated JSON metafield for product specs), and upload it to Shopify either via CSV import or through the Shopify Admin API. Key objectives include:

* Automate Data Retrieval: Download a zipped product CSV from an Etilize FTP server and extract it on a scheduled basis.

* Data Transformation: Combine multiple metadata columns from Etilize into a single JSON-formatted metafield (to store rich product specs) suitable for Shopify.

* Shopify Sync: Push the merged data directly to Shopify via the Admin API in batches.

* Scalability & Maintainability: Start with a simple script (for immediate needs), then evolve into a user-friendly web application with proper backend infrastructure for scheduling, logging, and user management.

The following document outlines the functional and technical requirements, a phased development roadmap, user stories, technology considerations, and deployment steps for the proposed system.

## **Functional Requirements**

1. FTP Data Download: The system shall connect to the Etilize FTP server using provided credentials, download the latest product data zip file, and extract the contained CSV. This process should be automated (e.g. run on a schedule) and log success or failure.

2. CSV Parsing & Metafield Generation: The system shall parse the Etilize CSV (which contains product info and numerous metafield columns). All columns representing product metadata (specifications, features, etc.) will be consolidated into a single JSON string under a custom metafield. For example, if the CSV has columns like Metafield: custom.Physical Characteristics\[length\] or similar, those will be merged into a JSON structure under a common namespace/key (e.g. custom.product\_info). This JSON will be stored as a text string to later upload to Shopify as a product metafield.

3. Data Merge & Enrichment: For each product present in the Etilize feed, the system shall update or create the product in Shopify

4. Output to Shopify: 

   * Direct API Push: Use the Shopify Admin API to create or update products in Shopify. This involves sending HTTP requests to Shopify’s API with the product data. Products will be created/updated in batches to respect rate limits (e.g., processing, say, 50 products per batch). Metafields must be handled via the API either by including them in the product creation payload or by a separate API call for each product’s metafield .

5. Logging & Error Handling: All steps (FTP download, parsing, API calls, etc.) should be logged. Errors (e.g., network issues, missing data for a product, API errors) must be captured and reported so that the process can be monitored and issues addressed. In later phases, these logs will be stored in a database and visible in the dashboard.

6. User Interface (Phase 2+): Develop a web dashboard that allows authorized users to:

   * Manually trigger a sync (start the FTP fetch, merge, and Shopify push process on demand).

   * View recent sync logs and statuses (success, error messages, timestamp).

   * Configure scheduling options (e.g., set the job to run daily at midnight).

   * (Optional) Provide configuration inputs, such as FTP credentials or API keys, if not stored as environment variables.

7. Authentication & Security: By Phase 3, the dashboard must be protected by user authentication. Only authorized personnel should be able to trigger syncs or view data. Use secure storage for credentials (never hard-code API keys in client-side code). The system should comply with Shopify API access requirements (using private app credentials or access tokens) 

8. Scalability & Maintainability: The design should allow adding new data sources or adjusting mapping with minimal changes. It should handle large CSV files efficiently (e.g., use streaming or chunked processing for thousands of products to avoid high memory usage). The pipeline should be robust against partial failures (e.g., if some products fail to upload, log and continue with others).

## **Technical Requirements & Specifications**

Tech Stack Considerations: The project can be implemented in either Python or JavaScript (Node.js) for the backend script. Key factors:

* Libraries & Ecosystem: Python offers powerful libraries like pandas for CSV processing and easy JSON handling, which can simplify merging and transformation (as evidenced by the provided create\_metafields.py script using pandas). On the other hand, Node.js has a rich ecosystem for FTP, CSV parsing, and direct integration with web frameworks (useful as we move to a web dashboard).

* Performance: Both languages can handle the tasks, but Python’s data manipulation might be faster for heavy CSV transformations in-memory, whereas Node can stream data to manage memory usage effectively. For thousands of products, either can work if coded properly.

* Integration: The later phases include a React frontend (JavaScript) and a Supabase backend. Choosing JavaScript/TypeScript for the backend might allow sharing code or types between backend and frontend, and potentially running the pipeline as a serverless function in the Supabase environment. Python, however, could still be used as a separate service.

* Developer Expertise: Given the existing sample code in Python and the quick scripting needs for Phase 1, a Python script might be the fastest to implement initially. However, for the long term, a Node.js service might integrate more smoothly with the Supabase/React stack.

Decision: For Phase 1, we will implement the sync script in Python (leveraging its simplicity for data processing). In Phase 2/3, as we build the web service, we can either encapsulate the Python script on the server (calling it as a subprocess or converting it to an API via a lightweight framework like FastAPI) or refactor into Node.js if needed for closer integration with the web stack. Both approaches will be evaluated; the plan will keep the code modular to allow a possible migration to Node later.

Environment & Tools:

* Python 3.x (for initial script) with libraries: ftplib (for FTP), pandas or csv (for parsing CSV), requests (for Shopify API calls), zipfile (to extract zip), etc.

* Node.js (if chosen for refactor) with packages: basic-ftp or ftp (for FTP), csv-parser or Papaparse (for CSV), and Shopify API library or Axios for API calls.

* React (TypeScript) for the frontend dashboard, utilizing Shadcn/UI (a component library built on Radix and Tailwind CSS) for a sleek UI.

* Supabase (PostgreSQL) for managing persistent data in Phase 3 – including tables for users, logs, and schedules. Supabase’s built-in Auth will manage user login, and its client library (@supabase/supabase-js) will be used in the React app for authentication and data queries.

* Shopify Admin API credentials: A Private App or Custom App on Shopify will provide API Key and Admin API access token with permissions to read/write products and metafields.

Shopify API Details:

* We will primarily use the Shopify REST Admin API for simplicity. To create a product via API, we send a POST request to the endpoint /admin/api/2023-04/products.json (for example) with a JSON payload containing the product data . Authentication is done by including the Shopify access token in the header (X-Shopify-Access-Token) .

* Example product creation payload (simplified):

{  
  "product": {  
    "title": "Example Product",  
    "body\_html": "\<p\>Product description\</p\>",  
    "vendor": "VendorName",  
    "tags": "Tag1, Tag2",  
    "variants": \[  
      {  
        "sku": "12345",  
        "price": "19.99",  
        "inventory\_quantity": 100  
      }  
    \],  
    "metafields": \[  
      {  
        "namespace": "custom",  
        "key": "product\_info",  
        "type": "json",  
        "value": "{\\"Color\\":\\"Clear\\",\\"Alcohol Free\\":\\"Yes\\"}"   
      }  
    \]  
  }  
}

* This would create a new product with one variant and attach a JSON metafield. (Note: The metafield value for type json can be provided as a JSON string. In newer API versions, Shopify may accept an actual object for JSON type via GraphQL, but with REST it’s safest to send it as a string-encoded JSON.)

* Metafield Sync: We must ensure the metafield definition exists in Shopify for our custom.product\_info key with type JSON. Typically, this is done in the Shopify admin under Settings \> Metafields before import . Once defined, we can set values via the API. If not including metafields on initial product creation, we can do a separate call: POST /admin/api/2023-04/products/{product\_id}/metafields.json with body {"metafield": { "namespace": "custom", "key": "product\_info", "type": "json", "value": "{...json...}" }} .

* Batching & Rate Limits: Shopify REST API allows 2 calls per second for private apps (or more for public apps with leaky bucket algorithm). Given potentially hundreds of products, we will implement batching (e.g., process 50 at a time with slight delays) and use Shopify’s Bulk Operations API for very large data sets if needed . The Bulk Operations GraphQL API can import many products in one job, though initial phases may stick to REST for simplicity. We will also implement retry logic and respect HTTP response headers that indicate call limits to avoid hitting the caps .

Data Mapping & Storage:

* Identifier Matching: We anticipate using the SKU or Manufacturer Part Number as the link between Etilize and Shopify \- this should be the handle in the shopify system. We will confirm which field is consistently present in both feeds and use that. The system should allow configuration of the matching key in case adjustments are needed.

* Data Transformations: The Etilize feed contains HTML in some fields (like product descriptions or feature lists). These can largely be passed through to Shopify’s Body (HTML) field as-is.   
* JSON Metafield Structure: The consolidated JSON will have a structure combining various specs. For example:

{  
  "metafield": {  
    "namespace": "custom",  
    "key": "product\_info",  
    "type": "json",  
    "value": {  
      "General Information": {  
        "Manufacturer": "Empack Spraytech, Inc",  
        "Product Name": "Foaming Hand Sanitizer 550 ml \- 70%"  
      },  
      "Physical Characteristics": {  
        "Color Family": "Clear",  
        "Product Color": "Clear"  
      },  
      "Miscellaneous": {  
        "Certifications & Standards": "DIN \# 2459272",  
        "Country of Origin": "Canada"  
      }  
    }  
  }  
}

* In our CSV, these might have come as separate metafield columns which we combine. The example shows a nested JSON (keys like “General Information”, “Physical Characteristics” come from the section headings in the data). Our script will need to handle nested keys (e.g. a column named Metafield: custom.General Information.Manufacturer will be nested accordingly). The provided script already demonstrates creating nested JSON if column names contain periods. The final JSON string will be stored in a column (for CSV output) or used directly in the API call.

* Shopify CSV Format: If outputting to CSV, the file must conform to Shopify’s import format. The product\_template.csv provided shows the required columns (Handle, Title, Body HTML, Vendor, Tags, Option1 Name, Option1 Value, Variant SKU, Variant Price, Variant Inventory Qty, etc.). Our merged data must be arranged to fit this structure. Products with single variants will have one line; if multi-variant (not evident in the sample data, but future-proofing), multiple lines with the same Handle will be needed. The JSON metafield can’t be directly imported via CSV to Shopify’s admin (Shopify’s CSV import doesn’t support metafields in older versions), so CSV output might be primarily for review or backup. Direct API is needed to attach metafields unless a separate metafield import process is used.

## **Phased Development Roadmap**

We will implement the system in three phases, delivering incremental value:

### **Phase 1: Backend Sync Script (MVP)**

Goal: Build a working script that can perform the end-to-end data sync manually (run on demand). This addresses immediate needs for data import and validates the approach.

* Implementation: Develop a Python script (or Node script, but Python chosen as per discussion) that:

  1. Fetches the Etilize Feed: Connect via FTP to Etilize, download the latest ZIP file containing the product CSV. Use environment variables or config files for FTP host, path, username, and password. For example, using Python’s ftplib:

from ftplib import FTP  
ftp \= FTP(ETILIZE\_FTP\_HOST)  
ftp.login(user=FTP\_USER, passwd=FTP\_PASS)  
with open('product\_feed.zip', 'wb') as f:  
    ftp.retrbinary(f"RETR {ETILIZE\_REMOTE\_PATH}", f.write)  
ftp.quit()  
\# Extract ZIP  
import zipfile  
with zipfile.ZipFile('product\_feed.zip', 'r') as zip\_ref:  
    zip\_ref.extractall('./data')

1. This will leave us with Etilize.csv (actual filename assumed) in a data folder.

   2. Parses and Processes Etilize CSV: Read the CSV (which may be large) in chunks using pandas or Python’s CSV module. Identify all columns that are metafields (they may be prefixed consistently, e.g., “Metafield: custom.” as in the sample). Use a function to merge these columns into one JSON. For example:

import pandas as pd, json  
df \= pd.read\_csv('Etilize.csv', dtype=str)  \# read as string to preserve data  
meta\_cols \= \[c for c in df.columns if c.startswith('Metafield: custom.')\]  
def create\_metafield\_json(row):  
    value \= {}  
    for col in meta\_cols:  
        key \= col.replace('Metafield: custom.', '').replace('\[list.single\_line\_text\]', '')  
        if pd.notna(row\[col\]) and row\[col\] \!= "":  
            \# handle nested keys denoted by dot notation  
            if '.' in key:  
                parent, child \= key.split('.', 1\)  
                value.setdefault(parent, {})\[child\] \= row\[col\]  
            else:  
                value\[key\] \= row\[col\]  
    metafield \= {  
        "namespace": "custom",  
        "key": "product\_info",  
        "type": "json",  
        "value": value  
    }  
    return json.dumps(metafield)  
df\['metafield\_json'\] \= df.apply(create\_metafield\_json, axis=1)

2. This snippet (inspired by the provided create\_metafields.py) goes through each row and builds a nested dictionary for the metafield values, then dumps it as JSON string. We add this as a new column metafield\_json to the DataFrame.

   3. (We will adjust column names based on actual header; the sample’s header indicates multiple price columns. Possibly StandardUnitPrice is the main price and inventory might be derived from other fields or assumed 100% in stock if ActiveFlag is true. We will confirm with the actual data.)

   4. Merge Datasets: Use pandas merge to combine Etilize If we assume the key is SKU which appears as SKU in Etilize

merged\_df \= pd.merge(df, xoro\_df, how='left', left\_on='SKU', right\_on='ItemNumber')

4. We expect most Etilize SKUs to find a match. For any mismatches, log a warning The merged dataframe now has both the product info and the pricing/inventory.

   5. Output to Shopify:

      * Shopify API Push: Use Python’s requests or a Shopify Python API client to send data to Shopify. For example, using REST API:

import requests  
shop\_url \= "https://{SHOP\_NAME}.myshopify.com/admin/api/2023-04/products.json"  
headers \= {"X-Shopify-Access-Token": SHOPIFY\_API\_PASSWORD, "Content-Type": "application/json"}  
for \_, product in merged\_df.iterrows():  
    product\_payload \= {  
        "product": {  
            "title": product\['Title'\],  
            "body\_html": product\['Body (HTML)'\],  
            "vendor": product\['Vendor'\],  
            "tags": product\['Tags'\],  
            "variants": \[  
                {  
                    "sku": product\['SKU'\],  
                    "price": product\['StandardUnitPrice'\],  
                    "inventory\_quantity": int(product.get('QuantityOnHand', 0))  
                }  
            \],  
            "metafields": \[  
                json.loads(product\['metafield\_json'\])  \# this is the dict with namespace, key, etc.  
            \]  
        }  
    }  
    resp \= requests.post(shop\_url, json=product\_payload, headers=headers)  
    if resp.status\_code \!= 201:  
        log\_error(f"Failed to create {product\['SKU'\]}: {resp.status\_code} {resp.text}")

* This loop will iterate through each product and call the API. In practice, we’d batch this (e.g., group in sets of 50 and add time.sleep() between batches to respect rate limits). We also might use Shopify’s Inventory API separately if managing inventory across locations, but for a single location we can rely on the inventory\_quantity in the variant as shown (Shopify will assign it to the default location if using a single location setup).

  6. Logging: The script will print and/or write to a log file the steps and any errors. E.g., “Downloaded file successfully”, “Parsed X products”, “Matched Y products,”, “Uploaded product SKU 12345 to Shopify”, or errors like “Failed to upload SKU 67890 – API error 429 (rate limit)”. In Phase 1, logging can be simple console output or a local file.

* Outputs/Deliverables for Phase 1: A working script (e.g., sync\_products.py) that can be run manually to perform the entire pipeline. Also, documentation or README on how to run it (e.g., install requirements, provide config values). The business can use this to do an initial bulk import to Shopify or update existing listings.

Phase 1 Testing: We will test the script with the provided sample files first (ensuring the JSON metafield is formatted correctly, the merge works on sample SKUs, etc.). Then do a trial run on a subset of actual data (perhaps limit to a few products) to verify the Shopify integration (preferably on a development store).

### **Phase 2: Web-Based Dashboard (React \+ API)**

Goal: Create a user-friendly interface for controlling and monitoring the sync process, making it accessible to non-developers and allowing on-demand operations without running scripts manually.

* Architecture: We will introduce a frontend built with React (using TypeScript). For styling and components, we’ll use shadcn/ui, which provides a set of pre-built, accessible components (buttons, forms, tables, modals) that we can style consistently. The frontend will interact with a backend API that triggers the sync and serves data. This backend could be:

  * A lightweight Node.js/Express server or Next.js API route if we migrate the script to Node.

  * Or a wrapper around the existing Python script (for instance, running a FastAPI server or simply executing the script via a system call).

* Given that we plan for Supabase in Phase 3, one approach in Phase 2 is to already set up a simple Node backend that later can integrate with Supabase easily. Alternatively, we use Supabase from the start to handle some backend needs (like using Supabase Edge Functions for the sync logic). However, Supabase Edge Functions run on Deno (JavaScript), meaning the Python code would need conversion. Thus, likely we stick to a Node backend by Phase 2\.

* Features of Dashboard:

  * Manual Sync Trigger: A button on the UI to “Run Product Sync Now”. When clicked, it will call an API endpoint (e.g., POST /run-sync) on the backend. The backend will asynchronously start the sync process (perhaps spawn a background thread/task to do the heavy work so the HTTP response can return quickly with a confirmation). The UI should give immediate feedback (e.g., “Sync started…”).

  * Sync Status & Logs: A view (table or list) showing recent sync executions. This would include timestamp, number of products processed, success/fail status, and a link to view details (or at least a snippet of log output or any errors). The backend will need to store these log entries, possibly just in memory or a file for now. We might create a simple model like an array or JSON file that the backend updates with log summaries. The React app can poll an endpoint like GET /sync-history to retrieve this data.

  * FTP/API Config (if needed): Optionally, the dashboard could display or allow updating configuration like FTP host, API keys, etc. However, for security, we likely keep those in environment variables or in Supabase (Phase 3\) rather than editable via UI. In Phase 2, we might omit this and assume configuration is static.

  * Basic Authentication (interim): Since Phase 2 doesn’t yet have Supabase auth, we might implement a simple password protection for the dashboard (even a basic HTTP auth or a login page with a single shared credential) just to keep it non-public. This is a temporary measure until Supabase is integrated.

* Communication: The React frontend will use fetch/Axios calls to the backend. For example, triggering sync:

// Example using fetch in a React component  
const runSync \= async () \=\> {  
  setStatus("Starting sync...");  
  const response \= await fetch("/api/run-sync", { method: "POST" });  
  if (response.ok) {  
    setStatus("Sync is running. Refresh for updates.");  
  } else {  
    const error \= await response.text();  
    setStatus("Error starting sync: " \+ error);  
  }  
};

* The backend /api/run-sync would in turn start the Python script or Node process. If using Node, it might call the sync logic function directly. If using Python, one approach is to have the Node server execute a shell command to run the Python script and maybe capture its output.

* Shadcn/UI usage: We will utilize components for building the interface quickly:

  * Use a Card or Panel component to show the “Sync Now” button and status.

  * Use a Table component to list past sync runs (columns: Date, Result, Details).

  * Use Modal/Dialog component to show detailed logs if needed when clicking a run.

  * Use Forms for any configuration inputs.

* Shadcn/ui (which is essentially a collection of Radix UI components styled with Tailwind) will ensure we have a modern, cohesive look without building everything from scratch.

* Deliverables for Phase 2: A running web application available at, say, http://yourserver:3000/dashboard (or a given URL), where a user can log in (if auth implemented) and see the sync controls. The backend will likely run on the same server, exposing endpoints for the front end to use. We will provide documentation on how the front-end and back-end are set up (it could be a single Next.js app containing both API routes and React pages, or separate React static app \+ separate API server).

Phase 2 Testing: We’ll verify that pressing the sync button indeed triggers the process and updates the UI (perhaps by showing a new log entry when done). Test with partial and full data. Ensure the UI is responsive and handles concurrent usage (though likely only one user/admin at a time). We’ll also test edge cases like triggering a new sync while one is already running (the backend should probably prevent overlapping runs – possibly by returning an error or queueing the request).

### **Phase 3: Supabase Integration & Deployment Hardening**

Goal: Enhance the application with a robust backend infrastructure: user authentication, persistent storage of logs and configurations, scheduling capability, and prepare the system for production deployment on a VPS.

* Supabase (Backend-as-a-Service): We introduce Supabase as our primary backend. Supabase provides:

  * PostgreSQL Database: We’ll create tables such as:

    * users (although Supabase Auth will manage most user info, we might join with a profile table if needed).

    * sync\_logs – to store each sync run record: id, timestamp, status, summary (e.g., “120 products, 0 errors”), maybe a link to a more detailed log or the log text.

    * sync\_schedule – to store schedule settings (e.g., cron expression or next run time, active/inactive).

    * config – for any configurable values like FTP credentials, etc., if we choose to store them here (encrypted if sensitive).

  * Auth: We will use Supabase Auth (which is essentially a hosted GoTrue service) to handle sign-ups and logins. Likely we will have a pre-set admin user. The React app will include a login page that uses Supabase’s JavaScript client to authenticate:

import { createClient } from '@supabase/supabase-js';  
const supabase \= createClient(SUPABASE\_URL, SUPABASE\_ANON\_KEY);  
// ...  
const { error, data } \= await supabase.auth.signInWithPassword({  
  email: emailInput,  
  password: passwordInput,  
});

* On success, Supabase provides a session JWT which the client uses for subsequent requests (in a Next.js app, we might use the Supabase middleware to protect API routes, or if using a custom backend, validate the token).

  * Row Level Security & Policies: We will configure the database so that only authenticated users can read/write the relevant tables. For example, sync\_logs table can be read by our user, and inserted into by a service role (the backend).

  * Edge Functions (Optional): Supabase allows deploying serverless functions in TypeScript (Deno). We could port the sync logic into a Supabase function to run on schedule. However, given the complexity (especially if still in Python), we might instead use the VPS to run the job and just use Supabase for data storage. There is also a Supabase Cron extension that can schedule PostgreSQL procedures, but our sync is external. Alternatively, we run a cron job on the VPS that triggers a Supabase function or directly runs the script. We’ll evaluate the simplest robust solution:

    * Perhaps easiest: use the Linux cron on VPS to hit an authenticated endpoint (or run a local script) to start sync periodically, based on the schedule set in DB.

    * Or use Supabase Scheduled Functions (currently in preview) if the logic is in a JS function.

* Application Changes in Phase 3:

  * Replace Temporary Auth with Supabase Auth: Remove any placeholder login. The React app will have a login page. Once logged in, it will use the Supabase session to call Supabase or our backend. If using Next.js, we might have API routes that require the Supabase token (which can be verified). Another approach is a pure client-side app that uses Supabase client to interact with data (e.g., calling supabase.from('sync\_logs').select() directly from the client to load log history). Supabase’s fine-grained auth rules can allow this securely. We may opt for this simpler approach: the React app uses Supabase client for reading logs and writing config, and calls a protected function to run the sync.

  * Logging to Database: When the sync script runs (whether via an API call or cron), it should record the outcome in the sync\_logs table. If the sync is triggered by an API endpoint, that endpoint (running on the server) can do something like:

\# Pseudo-code for logging (if in Python script)  
import psycopg2  
conn \= psycopg2.connect(SUPABASE\_DB\_DSN)  
cur \= conn.cursor()  
cur.execute("INSERT INTO sync\_logs(status, total\_products, errors, run\_at) VALUES(%s,%s,%s,NOW())",  
            ("success", total\_count, error\_count))  
conn.commit()

* If using Node, similarly use a PostgreSQL client (Supabase provides connection info).

   Alternatively, Supabase allows RESTful insert via its PostgREST (but using that from the server might not be necessary if we can connect directly).

   Each log entry can store aggregated info and maybe a URL or reference to a detailed log file if we don’t want to store huge text in the DB. For most runs, summary info is enough; we can keep full logs on disk (rotated files) or maybe in an S3 bucket if needed.

  * Schedule Enforcement: We create a UI in the dashboard for schedule config (e.g., a form to input desired interval, such as daily at 2 AM). This would update the sync\_schedule table. The actual scheduling can be implemented in a couple ways:

    * Use Supabase cron: If we deploy the sync as a Supabase Edge Function, we could use Supabase’s scheduled triggers to call it.

    * Or use the VPS’s cron: The cron job can run a small script every X minutes that checks sync\_schedule table to decide whether to run now (for example, if next\_run \<= now, then trigger sync and update next\_run). For reliability, a straightforward approach is to have a fixed cron schedule (like every hour) and within the script decide to actually run or not based on schedule settings.

    * Another approach: If we maintain a persistent server process (like our Node backend), it could internally use setInterval or a scheduling library to run at specified times. It would query the DB for the schedule or listen for changes (Supabase has real-time subscriptions, but that might be overkill for schedule).

    * We’ll choose a method that is simplest: likely a Linux cron entry for the desired times (updated manually whenever schedule changes, or dynamically via a small script).

  * Deployment & DevOps: By this phase, the project consists of multiple pieces – the web frontend, the backend logic, and the Supabase cloud services. We will provide instructions to deploy all parts on a VPS:

    * Setting up the environment (install Node, Python, Docker if needed, etc.).

    * Running the React build and serving it (possibly behind Nginx or as a static site).

    * Running the backend API (if Node, run it with a process manager like PM2 or systemd; if we rely purely on Supabase functions for triggering sync, maybe no persistent backend needed except for static file serving).

    * Ensuring environment variables (Shopify API keys, Supabase service key, etc.) are securely stored on the server (e.g., in a .env file not checked into code, loaded by the service).

    * Setting up SSL for the dashboard (if served over web, we should secure it).

    * Locking down the server (firewall rules so that, e.g., database ports are not open, only needed ports like 80/443 for the UI and maybe 22 for SSH).

    * Monitoring: set up some basic monitors or alerts (could be as simple as an email if a cron job fails, or using a tool like cron job monitoring service or Supabase Monitoring for function failures).

* Deliverables for Phase 3:

  * Fully functional web application with user authentication.

  * Automated daily (or scheduled) syncs happening without manual intervention.

  * Documentation on system architecture and how each component (frontend, backend script, Supabase) interacts.

  * Deployment guide (see below) and possibly scripts/Infrastructure-as-code for setting up (if time allows, e.g., a Dockerfile for the Node app, etc.).

Phase 3 Testing: We will test user login flows, ensure that without login the data can’t be accessed. Test that scheduling a sync does result in the sync running at the next interval (may simulate by setting a cron 2 minutes ahead, etc.). Test that logs appear in the dashboard correctly from the database. Also perform a full production-like test of a sync with the real data to ensure performance is acceptable on the VPS.

## **Conclusion**

This plan provides a comprehensive roadmap to implement the product feed integration system from initial script to a full-fledged web application with persistent backend support. By proceeding through the phases, we ensure we deliver immediate value (bulk product import) and then layer on usability, reliability, and security features. Using proven technologies and Shopify’s Admin API for product and metafield management – the system will greatly streamline the previously manual process of updating Shopify with rich product data .

With proper testing and iterative development, the end result will be a maintainable pipeline that keeps the Shopify store’s product catalog in sync with source data, reducing errors and saving time for the team.

