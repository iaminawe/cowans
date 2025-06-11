```markdown
# Zero-Code User Blueprint for SPARC Program Generation

**Project Title:** Product Feed Integration System for Shopify
**Prepared By:** Information extracted from "Product Feed Integration System – Development Plan & Requirements" document.
**Date:** May 29, 2025


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