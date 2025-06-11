Okay, I will now proceed with generating the Product Requirements Document (PRD) based on the "Zero-Code User Blueprint" you provided in the previous turn, which I filled out using the "Product Feed Integration System – Development Plan & Requirements" document.

I will follow the three-phase process you've outlined:
1.  **Phase 1:** Generate an initial PRD draft.
2.  **Phase 2:** Perform a self-critique of that draft.
3.  **Phase 3:** Revise based on the critique and output the final PRD.

Here is the "Zero-Code User Blueprint" that I will be using as the input for this process (this is the document I generated in our previous interaction):

```markdown
# Zero-Code User Blueprint for SPARC Program Generation

**Project Title:** Product Feed Integration System for Shopify
**Prepared By:** Information extracted from "Product Feed Integration System – Development Plan & Requirements" document.
**Date:** May 29, 2025

**Instructions for You (The Visionary!):**

* **No Tech Jargon Needed!** Just describe your idea in plain English. Think about what you want the program to do and why, not how it does it technically.
* **Be Detailed:** The more information and specific examples you give, the better the AI (our team of virtual coding assistants, called SPARC) can understand and build exactly what you want. Imagine you're describing it to someone who needs to build it perfectly without asking you follow-up questions.
* **Focus on the Goal:** What problem does this solve? What process does it make easier?
* **Don't Worry About Code:** SPARC will figure out the best programming languages, databases, and technical stuff based on your description and its own research.

---

## Section 1: The Big Picture - What is this program all about?

1.  **Elevator Pitch:** If you had 30 seconds to describe your program to a friend, what would you say? What's the main goal?
    * Your Answer: This program is designed to automatically get product information from a supplier (Etilize, via FTP) and put it into our Shopify store. The main goal is to build a solid system that fetches product data, combines it, creates a special JSON section for detailed product specs, and then uploads all of this to Shopify.
2.  **Problem Solver:** What specific problem does this program solve, or what task does it make much easier or better?
    * Your Answer: It solves the problem of manually updating Shopify with product data from Etilize, which is time-consuming and prone to errors. It automates the entire integration process.
3.  **Why Does This Need to Exist?** What's the key benefit it offers? (e.g., saves time, saves money, organizes information, connects people, provides entertainment, etc.)
    * Your Answer: The key benefits are saving a lot of time for the team, reducing errors in product listings, and generally making the process of keeping Shopify's product catalog up-to-date much smoother and more efficient.

---

## Section 2: The Users - Who is this program for?

1.  **Primary Users:** Describe the main type of person (or people) who will use this program. (e.g., small business owners, students, hobbyists, families, everyone, etc.)
    * Your Answer: The primary users will be authorized personnel or internal team members who are responsible for managing the product catalog and data in Shopify.
2.  **User Goals:** When someone uses your program, what are the top 1-3 things they want to accomplish with it?
    * Your Answer:
        * 1. Manually start a sync to update products on Shopify whenever needed.
        * 2. Check the history and status of recent product syncs to see if they worked correctly or if there were issues.
        * 3. Set up and change the schedule for when the product data should automatically update.

---

## Section 3: The Features - What can the program do?

1.  **Core Actions:** List the essential actions or tasks users can perform within the program. Be specific. Use action words.
    * Your Answer (List as many as needed):
        * Automatically connect to an FTP server to download product data files.
        * Extract product data from downloaded ZIP files and CSVs.
        * Read and understand product information from a CSV file.
        * Combine multiple product specification columns into a single JSON formatted field.
        * Create or update product listings in Shopify using its API.
        * Send product data to Shopify in batches to avoid overwhelming their system.
        * Keep a record (log) of all actions performed, including successes and failures.
        * (From Phase 2 onwards) Manually trigger the entire sync process through a web dashboard.
        * (From Phase 2 onwards) View logs and the status of recent syncs on the web dashboard.
        * (From Phase 2 onwards) Set or adjust the automatic sync schedule via the web dashboard.
        * (From Phase 3 onwards) Log into the web dashboard securely.
2.  **Key Feature Deep Dive:** Pick the MOST important feature from your list above. Describe step-by-step how you imagine someone using that specific feature from start to finish. What do they see? What do they click? What happens next?
    * Your Answer: Feature: Manually Triggering a Product Sync via Web Dashboard (Phase 2+)
        * The user logs into the web dashboard.
        * On the dashboard, they see a button like "Run Product Sync Now".
        * The user clicks this button.
        * The dashboard immediately shows a message like "Sync started..." or "Sync is running."
        * In the background, the system starts the process:
            * It connects to the Etilize FTP server.
            * It downloads the latest product data ZIP file and extracts the CSV.
            * It parses the CSV, paying special attention to columns that need to be grouped into a JSON metafield.
            * It prepares the product data (including this JSON metafield) for Shopify.
            * It sends the data to Shopify's Admin API to create new products or update existing ones, doing this in batches to respect Shopify's limits.
        * Throughout this process, the system is logging every step and any errors encountered.
        * When the sync is complete, the dashboard updates. The user can see a new entry in the sync history table, showing the date/time of the sync, whether it was successful or failed, how many products were processed, and a brief summary of any errors. They might be able to click for more detailed logs.

---

## Section 4: The Information - What does it need to handle?

1.  **Information Needed:** What kinds of information does the program need to work with, store, or display?
    * Your Answer (List all types):
        * Etilize FTP server credentials (host, path, username, password).
        * Shopify Admin API credentials (API Key, Admin API access token, Shop Name).
        * Product details from Etilize CSV: SKU, product title, product description (HTML), vendor name, product tags, various specification columns (e.g., color, dimensions, features), product price, inventory quantity.
        * The consolidated JSON metafield string (which itself contains product specs like 'Color', 'Manufacturer', etc.).
        * Information about each sync process: start time, end time, status (e.g., success, failure), number of products processed, error messages.
        * User account details for dashboard access (Phase 3): email, password.
        * Sync schedule settings (Phase 3): e.g., daily at a specific time.
2.  **Data Relationships (Optional but helpful):** Do any pieces of information naturally belong together?
    * Your Answer:
        * For each product, all its individual metadata/specification columns from the Etilize CSV are grouped together into a single JSON object, which then becomes a metafield for that product in Shopify.
        * Each product in Shopify has its main details (title, SKU, price, vendor, etc.) and this special JSON metafield containing richer product information.
        * Products can have different versions (variants), each with its own SKU, price, and inventory quantity.
        * Each sync attempt will have a corresponding log entry detailing its execution.
        * (In Phase 3) User accounts will be associated with login credentials and access rights to the dashboard.

---

## Section 5: The Look & Feel - How should it generally seem?

1.  **Overall Style:** Choose words that describe the general vibe. (e.g., Simple & Clean, Professional & Formal, Fun & Colorful, Modern & Minimalist, Artistic & Creative, Rugged & Outdoorsy)
    * Your Answer: Modern & Minimalist, Clean, Professional, User-Friendly. The plan mentions a "sleek UI" using Shadcn/UI.
2.  **Similar Programs (Appearance):** Are there any existing websites or apps whose look (not necessarily function) you like? Mentioning them helps the AI understand your visual preference.
    * Your Answer: Websites or dashboards built using Shadcn/UI components, which are based on Radix UI and Tailwind CSS. This implies a modern, component-based aesthetic.

---

## Section 6: The Platform - Where will it be used?

1.  **Primary Environment:** Where do you imagine most people using this program? (Choose one primary, others secondary if applicable)
    * [X] On a Website (accessed through Chrome, Safari, etc.) (This refers to the Phase 2+ dashboard)
    * [ ] As a Mobile App (on iPhone/iPad)
    * [ ] As a Mobile App (on Android phones/tablets)
    * [ ] As a Computer Program (installed on Windows)
    * [ ] As a Computer Program (installed on Mac)
    * [ ] Other (Please describe): The initial version (Phase 1) is a backend script run from a computer's command line or server environment.
    * Your Primary Choice & any Secondary Choices: Primary: Website (for user interaction via dashboard). The core processing engine is a backend script/service.
2.  **(If Mobile App):** Does it need to work without an internet connection sometimes? (Yes/No/Not Sure - AI will research implications)
    * Your Answer: N/A (It's a web-based dashboard and a server-side script, both requiring network access for their core functions – FTP, Shopify API).

---

## Section 7: The Rules & Boundaries - What are the non-negotiables?

1.  **Must-Have Rules:** Are there any critical rules the program must follow?
    * Your Answer:
        * The system must securely connect to the Etilize FTP server using the provided credentials.
        * It must download the specified product data zip file and correctly extract the CSV content.
        * All product metadata columns (as identified) must be consolidated into a single JSON string for the Shopify metafield.
        * It must use the Shopify Admin API to create or update products.
        * Product uploads/updates to Shopify must be done in batches to respect Shopify's API rate limits.
        * All key steps (FTP download, parsing, API calls) and any errors must be logged.
        * (By Phase 3) The web dashboard must require user login to access its features.
        * API keys and other sensitive credentials must be stored securely and never hard-coded in easily accessible parts like client-side code.
        * The system must use a designated field (like SKU or Manufacturer Part Number) to match products between the Etilize feed and Shopify.
2.  **Things to Avoid:** Is there anything the program should absolutely not do?
    * Your Answer:
        * Do not hard-code sensitive information like API keys or passwords directly into the client-side code or version control.
        * Do not make API calls to Shopify in a way that ignores or consistently violates rate limits, as this will cause failures.
        * (By Phase 3) Do not allow access to the sync triggering mechanism or logs by unauthorized users.

---

## Section 8: Success Criteria - How do we know it's perfect?

1.  **Definition of Done:** Describe 2-3 simple scenarios. If the program handles these scenarios exactly as described, you'd consider it a success for that part.
    * Your Scenarios:
        * 1. "When the sync process runs (either manually triggered from the dashboard or on a schedule), it successfully connects to the Etilize FTP, downloads and extracts the product CSV. It then processes each product, creates the combined JSON metafield, and successfully uploads the product data (creating new or updating existing) to Shopify via the API, respecting rate limits. A log is created confirming these actions and noting any errors for specific products." (Covers core end-to-end functionality).
        * 2. "An authorized user logs into the web dashboard, navigates to the 'manual sync' section, clicks 'Run Sync,' and sees immediate feedback that the sync has started. Later, they can view a history of syncs, find this specific run, and see its status (e.g., 'Completed successfully, 550 products updated, 0 errors') along with a timestamp."
        * 3. "(Phase 3) The system automatically runs a product sync at its scheduled time (e.g., daily at 2 AM). This sync completes the full Etilize to Shopify data integration without manual intervention, and the results (success/failure, products processed) are recorded in the database and visible on the dashboard's log history."

---

## Section 9: Inspirations & Comparisons - Learning from others

1.  **Similar Programs (Functionality):** Are there any existing programs, websites, or apps that do something similar to what you envision (even if only partly)?
    * Your Answer (List names if possible): The document doesn't name specific commercial off-the-shelf software it's trying to emulate or replace, but it describes a custom-built ETL (Extract, Transform, Load) pipeline. Conceptually, it's similar to functionalities found in some Product Information Management (PIM) systems that can syndicate data to e-commerce platforms, or complex data integration setups using tools like Apache NiFi, Talend, or even simpler automation platforms if they could handle the specific transformations and batching. However, the plan is clearly for a bespoke solution.
2.  **Likes & Dislikes:** For the programs listed above (or similar ones you know), what features or ways of doing things do you REALLY like? What do you REALLY dislike or find frustrating? This helps SPARC build something better.
    * Likes: The document implies a liking for systems that are "robust", "automated", "scalable & maintainable", "user-friendly" (for the dashboard part), handle large files "efficiently", and are "robust against partial failures". The detailed logging is also a desired positive trait.
    * Dislikes: The current process is described as "manual", error-prone, and time-consuming – these are the key dislikes the new system aims to eliminate.

---

## Section 10: Future Dreams (Optional) - Where could this go?

1.  **Nice-to-Haves:** Are there any features that aren't essential right now but would be great to add later?
    * Your Answer:
        * Allowing configuration of FTP or API keys directly through the UI dashboard (if security implications are handled).
        * Using Shopify’s Bulk Operations API for extremely large datasets.
        * Making it easier to add new data sources or adjust data mappings with minimal code changes.
        * Storing very detailed logs in a dedicated cloud storage like S3.
        * Potentially moving the sync logic to serverless functions (like Supabase Edge Functions) if performance and complexity allow.
        * Providing deployment scripts or Dockerfiles for easier setup.
2.  **Long-Term Vision:** Any thoughts on how this program might evolve in the distant future?
    * Your Answer: The long-term vision is to have a highly reliable and maintainable system that continuously keeps the Shopify product catalog perfectly in sync with product data sources. It could potentially expand to integrate more data sources beyond just Etilize, or perhaps even feed product data to other platforms beyond Shopify. More advanced data transformation capabilities, richer analytics on sync performance, and more sophisticated alerting could also be part of its future.

---

## Section 11: Technical Preferences (Strictly Optional!)

* **Note:** Our AI assistants are experts at choosing the best technical tools. Only fill this out if you have a very strong, specific reason for a particular choice (e.g., compatibility with an existing system you must use).

1.  **Specific Programming Language?** (e.g., Python, JavaScript, Java) Why?
    * Language: Python (for the initial backend sync script); React (TypeScript) (for the frontend dashboard); JavaScript/Node.js (as a potential option for refactoring the backend later).
    * Reason (Mandatory if language specified): Python was chosen for Phase 1 because of its strong data processing libraries (like pandas), ease of JSON handling, existing developer familiarity, and suitability for rapid scripting. React with TypeScript is for building the modern, interactive web dashboard. Node.js is considered for later phases for potentially better integration with the planned Supabase/React stack.
2.  **Specific Database?** (e.g., Supabase, PostgreSQL, MySQL) Why?
    * Database: Supabase (which uses PostgreSQL) for Phase 3.
    * Reason (Mandatory if database specified): Supabase is chosen for Phase 3 to manage persistent data like user accounts, sync logs, and schedules. Its built-in authentication features are also a key reason.
3.  **Specific Cloud Provider?** (e.g., Google Cloud, AWS, Azure) Why?
    * Provider: Supabase (as a Backend-as-a-Service), and deployment on a VPS (Virtual Private Server) for the application components.
    * Reason (Mandatory if provider specified): Supabase provides database and authentication services. A VPS is planned for hosting the frontend and backend application components, offering flexibility. No specific major cloud provider (AWS, Azure, GCP) is mandated for the VPS itself in the document.

---

**Final Check:**

* Have you answered all the questions in Sections 1-9 as clearly and detailed as possible? (Yes, based on the provided document)
* Have you used simple, everyday language? (Yes, while reflecting the source document's detail)
* Have you focused on the what and why? (Yes, as per the blueprint's intent)

**Ready to Build!**

Once you submit this completed blueprint, the SPARC orchestration will take over. It will:

1.  Use **Deep Research** to analyze your vision, explore similar programs, investigate technical options, and fill in any knowledge gaps.
2.  Use the **Specification Writer** to turn your answers and the research into formal requirements.
3.  Use the **github mcp tool** to do deep research on templates across github looking for any templates that might work for the project.
4.  Use the **Architect** to design the system structure.
5.  Use the **high level test deep research tool** to deep research all the best high level tests to make for the project.
6.  Have the **tester** create ALL of the high level tests.
7.  Use **Code, TDD, Supabase Admin, MCP Integration, and Security Reviewer modes** iteratively to build, test, and secure the program based on the specifications and architecture.
8.  Use the **System Integrator** to connect all the pieces.
9.  Use the **Documentation Writer** to create guides.
10. Use **DevOps** to set up infrastructure and deploy the application.
11. Finally, it will present the completed, working program to you based on the Success Criteria you provided!
```

---
**Phase 1: Initial PRD Draft Generation**
---

# Product Requirements Document: Product Feed Integration System for Shopify

**Version:** 1.0
**Date:** May 29, 2025
**Prepared For:** SPARC Development Team
**Prepared By:** AI Product Manager (based on Zero-Code User Blueprint)

## 1.0 Introduction & Vision

### 1.1 Project Overview
This document outlines the requirements for the Product Feed Integration System for Shopify. The system is designed to automate the process of retrieving product information from a supplier (Etilize, via FTP), transforming this data, and updating a Shopify store. The core function is to establish a robust pipeline that fetches product data, consolidates it (including creating a specialized JSON metafield for detailed product specifications), and then uploads this comprehensive data to Shopify. This project aims to replace a time-consuming and error-prone manual update process with an automated solution.

### 1.2 Goals & Objectives
The primary goal of this system is to automate the integration of product data from Etilize into Shopify, significantly streamlining the existing manual workflow.

**Objectives:**
* Automate the retrieval of product data from the Etilize FTP server.
* Automate the transformation of product data, including the generation of a consolidated JSON metafield for product specifications.
* Automate the creation and updating of products in Shopify using the Shopify Admin API.
* Reduce the time spent by the team on manual product data updates.
* Minimize errors in Shopify product listings that result from manual data entry.
* Improve the overall efficiency and reliability of maintaining an up-to-date product catalog on Shopify.
* Evolve from an initial script-based solution (MVP) to a user-friendly web application with features for scheduling, logging, and user management.

### 1.3 Target Audience & User Personas

**Target Audience:**
The primary users of this system will be authorized personnel and internal team members responsible for managing the Shopify store's product catalog and data.

**User Personas:**

* **Persona 1: Alex - E-commerce Content Manager**
    * **Responsibilities:** Ensuring product information on Shopify is accurate, complete, and up-to-date. Manages new product launches and updates to existing listings.
    * **Goals with this system:**
        * To quickly and easily trigger product data synchronization from Etilize to Shopify on demand.
        * To monitor the status and history of synchronization tasks to ensure data integrity.
        * To efficiently manage the scheduling of automated product data updates.
    * **Pain Points (current state):** Spends excessive time on manual data entry; high risk of errors; difficulty in keeping large catalogs consistently updated.

## 2.0 Functional Requirements

### 2.1 Core Features
The system will provide the following core features, evolving through planned development phases:

1.  **Automated FTP Data Retrieval:** The system will connect to a specified FTP server, download product data files (ZIP containing CSV), and extract them.
2.  **Data Parsing and Transformation:** The system will read and process product information from the extracted CSV files.
3.  **JSON Metafield Generation:** The system will combine multiple product specification columns from the CSV into a single JSON formatted metafield.
4.  **Shopify Product Synchronization:** The system will create or update product listings in Shopify using its Admin API.
5.  **Batch Processing:** The system will send product data to Shopify in batches to comply with API rate limits.
6.  **Comprehensive Logging:** The system will maintain logs of all significant actions, successes, and failures.
7.  **Manual Sync Trigger (Web Dashboard - Phase 2+):** Authorized users will be able to manually initiate the entire data synchronization process via a web-based dashboard.
8.  **Sync Monitoring (Web Dashboard - Phase 2+):** The dashboard will display logs and the status of recent synchronization tasks.
9.  **Schedule Configuration (Web Dashboard - Phase 2+):** Authorized users will be able to set up and adjust the schedule for automatic data synchronization via the dashboard.
10. **Secure User Authentication (Web Dashboard - Phase 3+):** The web dashboard will require secure user login.

### 2.2 Detailed Feature Breakdown (User Stories)

**Epic 1: Data Ingestion & Processing**

* **FS-1.1 (FTP Connection):** As a System Administrator, I want the system to securely connect to the Etilize FTP server using configured credentials so that product data files can be retrieved.
* **FS-1.2 (File Download & Extraction):** As a System, I want to automatically download the latest product data ZIP file from the FTP server and extract the CSV content so that it is ready for processing.
* **FS-1.3 (CSV Parsing):** As a System, I want to parse the extracted product CSV file, correctly interpreting rows and columns, so that individual product data can be accessed.
* **FS-1.4 (JSON Metafield Creation):** As a System, I want to consolidate multiple specified metadata columns from the CSV into a single, correctly formatted JSON string, representing a product metafield, so that rich product specifications can be stored in Shopify.
* **FS-1.5 (Product Data Matching):** As a System, I want to use a designated product identifier (e.g., SKU or Manufacturer Part Number) to match products from the Etilize feed with existing products in Shopify so that I can determine whether to create a new product or update an existing one.

**Epic 2: Shopify Integration**

* **FS-2.1 (Shopify API Product Creation):** As a System, I want to create new products in Shopify via the Admin API, including all standard product fields and the generated JSON metafield, so that new products from the feed are added to the store.
* **FS-2.2 (Shopify API Product Update):** As a System, I want to update existing products in Shopify via the Admin API, modifying relevant fields and the JSON metafield based on the incoming feed data, so that product information remains current.
* **FS-2.3 (Batch Processing & Rate Limit Management):** As a System, I want to send product creation/update requests to the Shopify Admin API in batches and respect API rate limits so that the synchronization process is reliable and does not get blocked.

**Epic 3: Logging & Monitoring**

* **FS-3.1 (Operational Logging):** As a System, I want to log all significant operations (e.g., FTP connection, file download, parsing, API requests) and their outcomes (success/failure), including any error details, so that system activity can be tracked and issues can be diagnosed.
* **FS-3.2 (Persistent Log Storage - Phase 3+):** As a System, I want to store sync logs persistently in a database so that historical sync information is available for review.

**Epic 4: Web Dashboard Functionality (Phase 2 onwards)**

* **FS-4.1 (Manual Sync Trigger):** As an E-commerce Content Manager, I want to be able to click a "Run Product Sync Now" button on the web dashboard so that I can initiate a full data synchronization from Etilize to Shopify on demand.
    * *User Interaction Flow for FS-4.1:*
        1.  User logs into the web dashboard.
        2.  User navigates to the sync control section.
        3.  User sees a clearly labeled button (e.g., "Run Product Sync Now").
        4.  User clicks the button.
        5.  The dashboard displays immediate feedback (e.g., "Sync started...", "Sync is running.").
        6.  The backend system initiates the FTP download, data processing, and Shopify API push.
        7.  The system logs all steps and errors during the background process.
        8.  Upon completion (or failure), the dashboard updates to reflect the sync status.
* **FS-4.2 (Sync History Display):** As an E-commerce Content Manager, I want to view a history of recent sync executions on the dashboard, including timestamps, status (success/failure), number of products processed, and a summary of errors, so that I can monitor the health and effectiveness of the synchronization process.
* **FS-4.3 (Detailed Log Access - Optional):** As an E-commerce Content Manager, I want to be able to click on a sync history entry to view more detailed logs for that specific run so that I can investigate any issues.
* **FS-4.4 (Schedule Configuration Interface - Phase 2+):** As an E-commerce Content Manager, I want an interface on the web dashboard to set up and modify the schedule for automatic product syncs (e.g., daily at a specific time) so that I can control when updates occur without manual intervention.
* **FS-4.5 (Dashboard User Authentication - Phase 3+):** As a System Administrator, I want the web dashboard to require users to log in with secure credentials so that only authorized personnel can access sync controls and data.

### 2.3 Data Requirements

**Data to be Handled by the System:**
* **Credentials:**
    * Etilize FTP server credentials: host, path, username, password.
    * Shopify Admin API credentials: API Key, Admin API access token, Shop Name.
    * User account credentials for dashboard access (Phase 3): email, hashed password.
* **Product Data (from Etilize CSV):**
    * Product Identifiers: SKU, Manufacturer Part Number (for matching).
    * Core Product Information: Product title, description (Body HTML), vendor name, product tags.
    * Pricing & Inventory: Product price, inventory quantity.
    * Specifications/Metadata: Various columns representing product features, dimensions, color, etc., which will be consolidated.
* **Transformed Data:**
    * Consolidated JSON metafield string: A JSON object (stored or transmitted as a string) containing structured product specifications (e.g., {"Color": "Blue", "Material": "Cotton"}).
* **Operational Data:**
    * Sync Process Logs: Timestamps (start time, end time), status (e.g., "Success", "Failure", "In Progress"), number of products processed, detailed error messages, summary messages.
    * Sync Schedule Configuration (Phase 3): Scheduling parameters (e.g., cron expression, frequency, next run time, active/inactive status).

**Data Relationships:**
* Each product from the Etilize CSV feed has multiple metadata attributes that are to be combined into a single JSON metafield object. This JSON metafield is then associated with that specific product in Shopify.
* A product in Shopify consists of standard fields (title, vendor, SKU, variants, etc.) and the custom JSON metafield containing the enriched Etilize specifications.
* Products may have multiple variants, each with its own SKU, price, and inventory data.
* Each data synchronization attempt (a "sync run") will have one or more corresponding log entries detailing its execution steps, status, and any errors.
* (Phase 3) User accounts in the system will be associated with their authentication credentials (managed by Supabase Auth) and permissions for accessing dashboard features.

## 3.0 Non-Functional Requirements

### 3.1 User Interface (UI) & User Experience (UX)
* **NFR-UI-1 (Overall Style):** The web dashboard shall have a Modern & Minimalist, Clean, Professional, and User-Friendly design.
* **NFR-UI-2 (Appearance Inspiration):** The UI design should take inspiration from websites or dashboards built with Shadcn/UI components, emphasizing a modern, component-based aesthetic that is intuitive to navigate.
* **NFR-UI-3 (Responsiveness):** The web dashboard should be responsive and accessible on standard desktop web browsers (e.g., Chrome, Safari, Firefox, Edge).
* **NFR-UI-4 (Feedback):** The system shall provide clear and timely feedback to users for actions performed via the dashboard (e.g., initiating a sync, saving schedule settings).

### 3.2 Platform & Environment
* **NFR-PL-1 (Primary User Interaction Environment):** The primary environment for user interaction (manual sync, monitoring, scheduling) will be a web-based dashboard accessed through standard desktop web browsers.
* **NFR-PL-2 (Backend Processing Environment):** The core data processing engine will initially be a backend script (Phase 1) run from a server environment, evolving to a backend service supporting the web dashboard.
* **NFR-PL-3 (Internet Connectivity):** The system (both backend processing and web dashboard) requires internet connectivity to access the Etilize FTP server and the Shopify Admin API. Offline operation is not a requirement.
* **NFR-PL-4 (Technology Stack - Phase 1 Backend):** Python, leveraging libraries like pandas for CSV processing and JSON handling.
* **NFR-PL-5 (Technology Stack - Frontend Dashboard - Phase 2+):** React with TypeScript, utilizing Shadcn/UI.
* **NFR-PL-6 (Technology Stack - Backend API & Persistence - Phase 3+):** Node.js (potential for backend refactor) with Supabase (PostgreSQL) for database and authentication.
* **NFR-PL-7 (Deployment Environment - Phase 3+):** The application components are planned for deployment on a Virtual Private Server (VPS), with Supabase used as a BaaS.

### 3.3 Constraints & Business Rules
* **NFR-BR-1 (FTP Connection Security):** The system must connect to the Etilize FTP server securely using the provided credentials.
* **NFR-BR-2 (Data Integrity - Download & Extraction):** The system must download the specified product data ZIP file from Etilize and correctly extract the CSV content without data loss or corruption.
* **NFR-BR-3 (Data Integrity - Metafield Generation):** All designated product metadata columns from the Etilize CSV must be accurately consolidated into a single JSON string for the Shopify metafield, preserving data types where possible or converting appropriately.
* **NFR-BR-4 (Shopify API Usage):** The system must use the Shopify Admin API for creating or updating products.
* **NFR-BR-5 (Shopify API Rate Limits):** Product uploads/updates to Shopify must be performed in batches, and the system must implement mechanisms to respect Shopify's API rate limits to prevent service disruption.
* **NFR-BR-6 (Logging Mandate):** All key operational steps (FTP download, parsing, API calls) and any resulting errors must be comprehensively logged.
* **NFR-BR-7 (Product Matching Logic):** The system must use a designated field (e.g., SKU or Manufacturer Part Number, to be confirmed based on data consistency) to reliably match products between the Etilize feed and existing Shopify products.

### 3.4 Security & Privacy Considerations
* **NFR-SEC-1 (Credential Security):** API keys, FTP passwords, and other sensitive credentials must be stored securely (e.g., using environment variables, or encrypted storage in Supabase) and must NOT be hard-coded into source code, especially client-side code or version-controlled files.
* **NFR-SEC-2 (Authenticated Dashboard Access - Phase 3+):** Access to the web dashboard, particularly features for triggering syncs, viewing detailed logs, and configuring schedules, must be protected by a robust user authentication mechanism. Only authorized users should have access.
* **NFR-SEC-3 (Protection Against Unauthorized Sync Triggering - Phase 3+):** The system must prevent unauthorized users from initiating data synchronization processes or accessing sensitive log information.
* **NFR-SEC-4 (Data in Transit):** Communication with external services (FTP, Shopify API, Supabase) should use secure protocols (e.g., SFTP if available instead of FTP, HTTPS for API calls). (Assumption: Standard FTP is used for Etilize as per "FTP server" mention, HTTPS for Shopify/Supabase).
* **NFR-SEC-5 (Session Management - Phase 3+):** Secure session management practices must be implemented for the web dashboard to prevent session hijacking or fixation. (Leverage Supabase Auth capabilities).

## 4.0 Success Criteria & Acceptance Criteria

The system's success will be measured by its ability to meet the scenarios outlined in the "Definition of Done" from the blueprint. These are expanded into more detailed acceptance criteria below.

**SC-1: Successful End-to-End Automated Product Sync (Manual or Scheduled)**
* **Given** the system is configured with valid Etilize FTP and Shopify API credentials,
* **When** a product synchronization process is initiated (either manually from the dashboard or via an automated schedule),
* **Then** the system successfully connects to the Etilize FTP server.
* **And** the system downloads the latest product data ZIP file and correctly extracts the CSV content.
* **And** the system accurately parses the CSV data.
* **And** the system correctly identifies and processes products, creating a consolidated JSON metafield for each product's specifications.
* **And** the system successfully uploads the product data (creating new products or updating existing ones) to the Shopify store via the Shopify Admin API.
* **And** the system respects Shopify API rate limits through batching or other control mechanisms.
* **And** a comprehensive log entry is created for the sync run, confirming the actions performed, the number of products processed, and detailing any errors encountered for specific products.

**SC-2: Successful Manual Sync Operation via Web Dashboard (Phase 2+)**
* **Given** an authorized user is logged into the web dashboard,
* **And** the user navigates to the manual sync section,
* **When** the user clicks the "Run Sync" (or similarly labeled) button,
* **Then** the dashboard provides immediate visual feedback indicating that the sync process has started.
* **And** the backend system initiates the full end-to-end product sync process.
* **And** upon completion of the sync, the user can view an updated entry in the sync history on the dashboard.
* **And** this sync history entry accurately displays the timestamp, status (e.g., "Completed successfully" or "Failed"), the total number of products processed, and a summary of any errors.

**SC-3: Successful Automated Scheduled Sync (Phase 3+)**
* **Given** a sync schedule is configured in the system (e.g., daily at 2 AM),
* **And** the system is operational,
* **When** the scheduled time for the sync arrives,
* **Then** the system automatically initiates and completes the full Etilize to Shopify data integration process without requiring any manual intervention.
* **And** the results of this automated sync (including status, products processed, and any errors) are recorded persistently in the database.
* **And** these results are visible and accurately reflected in the sync history log on the web dashboard.

**SC-4: Secure Dashboard Access (Phase 3+)**
* **Given** the web dashboard URL is accessed,
* **When** a user attempts to access features for sync control or viewing detailed logs,
* **Then** the user is prompted to log in if they do not have an active authenticated session.
* **And** only users with valid, authorized credentials can successfully log in and access these protected features.
* **And** users without valid credentials or those not logged in are denied access to protected features.

## 5.0 Future Considerations / Roadmap

The initial development will focus on delivering the core functionality as outlined in the phased approach (Phase 1: Backend Script MVP; Phase 2: Web Dashboard; Phase 3: Supabase Integration & Hardening). Beyond this, the following features and enhancements are envisioned as future possibilities:

**Nice-to-Haves (Post-Core Implementation):**
* **NH-1 (UI Configuration Management):** Allow authorized users to configure certain parameters like FTP credentials or API keys directly through a secure section of the UI dashboard, rather than solely relying on environment variables (requires careful security assessment and implementation).
* **NH-2 (Shopify Bulk Operations API Integration):** For extremely large product datasets, investigate and potentially implement support for Shopify’s Bulk Operations API to improve sync efficiency and reliability.
* **NH-3 (Enhanced Data Mapping Flexibility):** Develop features that make it easier to add new data sources (beyond Etilize) or adjust data mapping rules between source fields and Shopify fields with minimal code changes, potentially through a UI.
* **NH-4 (Cloud-Based Detailed Log Storage):** Implement functionality to store very detailed or verbose logs in a dedicated cloud storage solution (e.g., AWS S3, Google Cloud Storage) for long-term archival and in-depth diagnostics, with summaries remaining in the primary database.
* **NH-5 (Serverless Sync Logic):** Explore migrating parts of the sync logic to serverless functions (e.g., Supabase Edge Functions, AWS Lambda, Google Cloud Functions) if performance, complexity, and maintenance benefits are evident.
* **NH-6 (Deployment Automation):** Provide deployment scripts (e.g., shell scripts, Ansible playbooks) or containerization configurations (e.g., Dockerfiles, Docker Compose files) to simplify and standardize the setup and deployment of the system.

**Long-Term Vision:**
* **LTV-1 (Multi-Source Integration):** Evolve the system to support integration with multiple product data sources beyond the initial Etilize feed.
* **LTV-2 (Multi-Platform Syndication):** Expand capabilities to feed processed product data to other e-commerce platforms or marketplaces beyond Shopify.
* **LTV-3 (Advanced Data Transformation & Enrichment):** Introduce more sophisticated data transformation rules, data validation, and data enrichment capabilities within the pipeline.
* **LTV-4 (Advanced Alerting & Recovery):** Implement more comprehensive error handling, automated alerting for sync failures or anomalies, and potentially semi-automated recovery mechanisms.
* **LTV-5 (Sync Analytics & Reporting):** Develop analytics features to provide insights into sync process performance, data quality trends, and the impact of updates on the product catalog.

## 6.0 Assumptions & Open Questions

**Assumptions:**
* **A-1:** The Etilize FTP server will be reliably accessible to the system.
* **A-2:** The product data CSV format from Etilize will remain consistent; any changes to the CSV structure would require corresponding updates to the system's parsing logic. (The plan notes "We will adjust column names based on actual header", implying an initial adaptation but assumes stability post-setup).
* **A-3:** The Shopify Admin API will be available and its core functionalities for product and metafield management will remain stable.
* **A-4:** A suitable field (SKU or Manufacturer Part Number) for uniquely identifying and matching products between Etilize and Shopify exists and is consistently populated in both systems. (The plan states "We will confirm which field is consistently present").
* **A-5:** The initial scope does not require handling product images directly through this pipeline unless they are simple links within the CSV data. (The blueprint focuses on textual and specification data).
* **A-6:** For Phase 1 (MVP script), manual execution in a server environment is acceptable.
* **A-7:** Standard FTP is acceptable for Etilize; SFTP is not explicitly required by the blueprint for this source.
* **A-8:** The definition for the `custom.product_info` JSON metafield will be pre-configured in the Shopify admin settings before the system attempts to write to it.

**Open Questions for the Visionary/Stakeholders:**
* **OQ-1:** What is the definitive, consistently populated unique identifier field in both Etilize and Shopify that should be used for product matching (e.g., SKU, Manufacturer Part Number)?
* **OQ-2:** Are there specific requirements for handling products that exist in Shopify but are no longer present in the Etilize feed (e.g., should they be disabled, deleted, or ignored)?
* **OQ-3:** What are the exact column names in the Etilize CSV that contain product price and inventory quantity? (The plan notes ambiguity, "Possibly StandardUnitPrice is the main price and inventory might be derived").
* **OQ-4:** What level of detail is required for error reporting in the dashboard logs for the average user versus an administrator?
* **OQ-5:** For scheduled syncs (Phase 3), what is the desired default frequency and time (e.g., daily at 2 AM)?
* **OQ-6:** How should the system behave if a sync is manually triggered while a scheduled sync is already in progress (or vice-versa)? Should one be queued, disallowed, or should they run in parallel (if technically feasible and safe)? (The Phase 2 testing plan mentions the backend should "probably prevent overlapping runs").
* **OQ-7:** Are there any specific compliance or data retention policies for the sync logs?

## 7.0 Out of Scope

The following items are considered out of scope for the initial core development (Phases 1-3) unless explicitly reprioritized:

* **OS-1: Product Image/Asset Management:** Direct uploading, hosting, or management of product image files or other digital assets. The system will handle image URLs if they are part of the text data in the CSV but will not process image binaries.
* **OS-2: Multi-Language Support:** The initial system will assume product data is in a single primary language.
* **OS-3: Complex Product Types:** Advanced Shopify product types beyond standard products and variants with metafields (e.g., subscription products, bundled products requiring app-specific logic) unless they can be managed through standard API fields/metafields.
* **OS-4: Real-time Bidirectional Sync:** The described system is primarily a one-way sync from Etilize to Shopify, triggered on demand or by schedule. Real-time updates or bidirectional synchronization are not in scope.
* **OS-5: Direct CSV Output as Primary Shopify Import Method:** While the plan mentions CSV output as a possibility for review or backup, the primary integration method with Shopify for creating/updating products with metafields is the Shopify Admin API. (Shopify's CSV import doesn't natively support metafields easily).
* **OS-6: User Role Management Beyond Admin:** For Phase 3, a single "authorized user" role is implied for dashboard access. Granular role-based access control (RBAC) with multiple permission levels is out of scope.
* **OS-7: Handling Orders, Customers, or other Shopify data entities:** The system is solely focused on product data integration.

---
**End of Phase 1: Initial PRD Draft Generation**
---

I will now proceed to Phase 2: Self-Critique and Evaluation.