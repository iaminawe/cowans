# Security Best Practices for Shopify API Credentials

This document outlines the best practices for securely storing and managing Shopify API credentials within the Product Feed Integration System.

## Secure Storage Solutions

*   **Avoid Hardcoding:** Never store API keys directly in the application code or configuration files. This is a major security risk. [2]
*   **Environment Variables:** Store sensitive information such as API keys and passwords in environment variables, which are not part of the codebase. This prevents accidental exposure in version control systems. [5][1]
*   **Secret Management Services:** Use dedicated secret management services such as AWS Secrets Manager, HashiCorp Vault, or CyberArk Conjur for enhanced security and centralized management. [5][1]

    *   **AWS Secrets Manager:** Enables automatic rotation of secrets, fine-grained access control using IAM policies, and encryption using AWS KMS. [2]
    *   **HashiCorp Vault:** Provides dynamic secrets, audit logging, and centralized secret management. [5]
    *   **CyberArk Conjur:** Focuses on machine identity management and provides secure storage and access control for secrets. [5]

## Access Control Fundamentals

*   **Principle of Least Privilege**: Assign only necessary API scopes for each API key. This limits the impact if a key is compromised. [1][2]
*   **IP Allowlisting**: Restrict API access to specific IP addresses or ranges to prevent unauthorized access from unknown sources. [4]
*   **Regular Key Rotation**:  
  ```bash
  # Rotate keys quarterly via Shopify Admin API
  POST /admin/api/2024-01/api_clients/{id}/rotate.json
  ```
  Implement automated rotation cycles (90-day recommended) [5]

## Authentication Protocols

*   **OAuth 2.0 Flow**  
  Using private apps is better for security.
  ```mermaid
  sequenceDiagram
    Client->>Shopify: Redirect to auth endpoint
    Shopify->>Client: Authorization code
    Client->>Shopify: Exchange code for token
    Shopify->>Client: Access token (expires in 24h)
  ```
    *   Prefer short-lived tokens (max 24h) over permanent API keys [2]  
    *   Use `X-Shopify-Access-Token` header with HTTPS **only** [2]

## Monitoring & Threat Detection

*   **Log Analysis**:  
  ```json
  // Sample API log alert rule
  {
    "filter": "status >= 400 AND api_path:/admin/products",
    "threshold": "5/minute",
    "action": "block_ip"
  }
  ```
  Implement real-time alerts for:  
    *   Spike in 401/403 errors [4]  
    *   Unusual geographic access patterns [3]  

*   **Bot Mitigation**:  
    Integrate reCAPTCHA v3 for public endpoints:  
    ```javascript
    grecaptcha.execute('SHOPIFY_FORM', {action: 'api_call'})
    ```

## Incident Response Planning

*   **Compromise Checklist**:  
    1.  Revoke exposed credentials via `DELETE /admin/api_clients/{id}.json` [1]  
    2.  Audit recent API logs for suspicious activity [4]  
    3.  Rotate all affected credentials [5]  

*   **Forensic Tools**:  
    *   Shopify Audit Log API endpoint  
    *   AWS CloudTrail for cloud secret access tracing

## Additional Recommendations

*   **Use Private Apps:** As mentioned in source \[4], where it says "It’s also worth noting that API keys are available for both public and private apps, but the latter is more secure. Public apps are designed to be installed by multiple users, increasing the risk of key exposure.", using Private apps instead of public apps limits exposure of credentials.
*   **Consider multi-factor authentication:** Require multi-factor authentication for any user accessing the credentials or the system. [3]