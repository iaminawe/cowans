# Sync System Flow Diagrams

## 1. Etilize Sync Workflow

```mermaid
sequenceDiagram
    participant FTP as Etilize FTP
    participant SM as Sync Manager
    participant XA as Xorosoft API
    participant DB as Supabase DB
    participant SS as Sync Staging
    participant UI as Dashboard UI
    
    Note over SM: Scheduled or Manual Trigger
    
    SM->>FTP: Check for new files
    FTP-->>SM: CowanOfficeSupplies.zip found
    
    SM->>FTP: Download file
    FTP-->>SM: File downloaded
    
    SM->>SM: Extract ZIP
    SM->>SM: Parse CSV
    
    loop For each product batch
        SM->>XA: Validate products (batch of 100)
        XA-->>SM: Validation results
        
        SM->>DB: Match with existing products
        DB-->>SM: Matching results
        
        alt Product exists
            SM->>SS: Create UPDATE staging entry
        else New product
            SM->>SS: Create CREATE staging entry
        end
    end
    
    SM->>SS: Auto-approve high confidence matches (>95%)
    SS->>UI: Notify pending approvals
    
    UI->>SS: Manual review/approval
    SS->>DB: Execute approved changes
```

## 2. Shopify Bidirectional Sync Flow

### 2.1 Sync Down (Shopify → Supabase)

```mermaid
flowchart TB
    subgraph "Shopify"
        SH[Shopify Products]
        SW[Webhooks]
    end
    
    subgraph "Sync Engine"
        SD[Sync Down Service]
        CD[Conflict Detector]
        VS[Version Service]
    end
    
    subgraph "Database"
        LP[Local Products]
        PV[Product Versions]
        SC[Sync Conflicts]
    end
    
    subgraph "Resolution"
        AR[Auto Resolver]
        MR[Manual Review]
    end
    
    SH -->|Fetch Updates| SD
    SW -->|Real-time Changes| SD
    
    SD -->|Check Existing| LP
    SD -->|Detect Changes| CD
    
    CD -->|No Conflict| VS
    CD -->|Conflict Found| SC
    
    VS -->|Create Version| PV
    VS -->|Update Product| LP
    
    SC -->|Auto-resolvable| AR
    SC -->|Manual Required| MR
    
    AR -->|Apply Resolution| LP
    MR -->|User Decision| LP
```

### 2.2 Staged Sync Up (Supabase → Shopify)

```mermaid
stateDiagram-v2
    [*] --> SelectProducts: User initiates sync
    
    SelectProducts --> CalculateChanges: Products selected
    
    CalculateChanges --> CreateStaging: Changes detected
    CalculateChanges --> NoChanges: No changes
    
    CreateStaging --> PendingReview: Staging entries created
    
    PendingReview --> Review: User reviews
    PendingReview --> AutoApprove: Auto-approval threshold met
    
    Review --> Approve: User approves
    Review --> Reject: User rejects
    Review --> PartialApprove: Mixed decision
    
    AutoApprove --> ExecuteSync
    Approve --> ExecuteSync
    PartialApprove --> ExecuteSync: Approved items only
    
    ExecuteSync --> SyncSuccess: Success
    ExecuteSync --> SyncFailed: Error
    
    SyncSuccess --> UpdateStatus: Mark as synced
    SyncFailed --> RetryQueue: Add to retry
    
    UpdateStatus --> [*]
    Reject --> [*]
    NoChanges --> [*]
    
    RetryQueue --> ExecuteSync: Retry attempt
```

## 3. Xorosoft Integration Flow

```mermaid
graph LR
    subgraph "Triggers"
        T1[Scheduled Job]
        T2[Manual Trigger]
        T3[Low Stock Alert]
    end
    
    subgraph "Xorosoft Sync"
        XS[Xorosoft Service]
        BL[Batch Lookup]
        IC[Inventory Check]
        VC[Validation Check]
    end
    
    subgraph "Data Processing"
        UP[Update Products]
        UX[Update Xorosoft Table]
        QS[Queue Shopify Updates]
    end
    
    subgraph "Shopify Updates"
        IU[Inventory Update]
        PU[Price Update]
        BU[Batch Update API]
    end
    
    T1 --> XS
    T2 --> XS
    T3 --> XS
    
    XS --> BL
    XS --> IC
    XS --> VC
    
    BL --> UP
    IC --> UP
    VC --> UP
    
    UP --> UX
    UP --> QS
    
    QS --> IU
    QS --> PU
    
    IU --> BU
    PU --> BU
```

## 4. Parallel Processing Architecture

```mermaid
graph TB
    subgraph "Operation Queue"
        PQ[Priority Queue]
        O1[High Priority Ops]
        O2[Normal Priority Ops]
        O3[Batch Ops]
    end
    
    subgraph "Worker Pool"
        WM[Worker Manager]
        W1[Worker 1]
        W2[Worker 2]
        W3[Worker 3]
        WN[Worker N]
    end
    
    subgraph "Processing"
        BO[Batch Optimizer]
        GQ[GraphQL Batcher]
        CC[Cache Controller]
    end
    
    subgraph "Results"
        RA[Result Aggregator]
        EM[Error Manager]
        PM[Progress Monitor]
    end
    
    PQ --> O1
    PQ --> O2
    PQ --> O3
    
    O1 --> WM
    O2 --> WM
    O3 --> WM
    
    WM --> W1
    WM --> W2
    WM --> W3
    WM --> WN
    
    W1 --> BO
    W2 --> BO
    W3 --> BO
    WN --> BO
    
    BO --> GQ
    BO --> CC
    
    GQ --> RA
    CC --> RA
    
    RA --> PM
    RA --> EM
```

## 5. Conflict Resolution Decision Tree

```mermaid
flowchart TD
    C[Conflict Detected]
    
    C --> T1{Field Type?}
    
    T1 -->|Price| P1{Price Difference}
    P1 -->|< 5%| AR1[Auto-resolve: Use Shopify]
    P1 -->|>= 5%| MR1[Manual Review Required]
    
    T1 -->|Inventory| I1{Stock Level}
    I1 -->|Shopify = 0| AR2[Auto-resolve: Use Xorosoft]
    I1 -->|Both > 0| I2{Difference}
    I2 -->|< 10 units| AR3[Auto-resolve: Use lower]
    I2 -->|>= 10 units| MR2[Manual Review Required]
    
    T1 -->|Description| D1{Source Priority}
    D1 -->|Etilize Updated| AR4[Auto-resolve: Use Etilize]
    D1 -->|Manual Edit| MR3[Manual Review Required]
    
    T1 -->|Other| O1{Has Priority Rule?}
    O1 -->|Yes| AR5[Apply Rule]
    O1 -->|No| MR4[Manual Review Required]
    
    AR1 --> R[Resolved]
    AR2 --> R
    AR3 --> R
    AR4 --> R
    AR5 --> R
    
    MR1 --> U[User Decision]
    MR2 --> U
    MR3 --> U
    MR4 --> U
    
    U --> R
```

## 6. Data Flow State Machine

```mermaid
stateDiagram-v2
    [*] --> Idle
    
    Idle --> FTPMonitoring: Start monitoring
    
    FTPMonitoring --> FileDetected: New file found
    FTPMonitoring --> FTPMonitoring: No new files
    
    FileDetected --> Downloading: Begin download
    
    Downloading --> Processing: Download complete
    Downloading --> Error: Download failed
    
    Processing --> XorosoftValidation: Parse CSV
    
    XorosoftValidation --> Matching: Validation complete
    XorosoftValidation --> Error: API error
    
    Matching --> StagingCreation: Products matched
    
    StagingCreation --> ReviewPending: Entries created
    
    ReviewPending --> AutoApproval: Confidence > threshold
    ReviewPending --> ManualReview: Requires approval
    
    AutoApproval --> Syncing
    ManualReview --> Syncing: Approved
    ManualReview --> Rejected: Rejected
    
    Syncing --> Complete: Sync successful
    Syncing --> Error: Sync failed
    
    Complete --> Idle
    Rejected --> Idle
    Error --> RetryWait
    
    RetryWait --> Idle: After delay
```

## 7. Performance Monitoring Dashboard

```mermaid
graph TB
    subgraph "Metrics Collection"
        MC1[Operation Metrics]
        MC2[API Metrics]
        MC3[Queue Metrics]
        MC4[Worker Metrics]
    end
    
    subgraph "Aggregation"
        TS[Time Series DB]
        MA[Metric Aggregator]
        AL[Alert Manager]
    end
    
    subgraph "Visualization"
        RT[Real-time Dashboard]
        HG[Historical Graphs]
        AB[Alert Banner]
    end
    
    subgraph "Alerts"
        EA[Email Alerts]
        SA[Slack Alerts]
        WH[Webhooks]
    end
    
    MC1 --> MA
    MC2 --> MA
    MC3 --> MA
    MC4 --> MA
    
    MA --> TS
    MA --> AL
    
    TS --> RT
    TS --> HG
    
    AL --> AB
    AL --> EA
    AL --> SA
    AL --> WH
```

## 8. Error Handling and Recovery

```mermaid
flowchart TD
    E[Error Occurred]
    
    E --> ET{Error Type}
    
    ET -->|Network| N1{Retryable?}
    N1 -->|Yes| R1[Exponential Backoff]
    N1 -->|No| F1[Mark Failed]
    
    ET -->|Validation| V1{Data Issue?}
    V1 -->|Missing Field| FX1[Apply Default]
    V1 -->|Invalid Format| FX2[Transform Data]
    V1 -->|Cannot Fix| F2[Skip Item]
    
    ET -->|API Limit| L1[Rate Limiter]
    L1 --> W1[Wait Period]
    W1 --> R2[Retry]
    
    ET -->|Database| D1{Connection?}
    D1 -->|Lost| RC1[Reconnect]
    D1 -->|Deadlock| RT1[Retry Transaction]
    
    ET -->|Unknown| U1[Log Error]
    U1 --> N2[Notify Admin]
    U1 --> F3[Mark Failed]
    
    R1 --> S[Success]
    R2 --> S
    RC1 --> S
    RT1 --> S
    FX1 --> S
    FX2 --> S
    
    F1 --> DLQ[Dead Letter Queue]
    F2 --> DLQ
    F3 --> DLQ
    
    DLQ --> MR[Manual Resolution]
```

## 9. Security and Audit Flow

```mermaid
sequenceDiagram
    participant U as User
    participant API as API Gateway
    participant Auth as Auth Service
    participant Sync as Sync Service
    participant Audit as Audit Log
    participant DB as Database
    
    U->>API: Request sync operation
    API->>Auth: Validate JWT token
    Auth-->>API: Token valid + permissions
    
    API->>Sync: Execute sync with user context
    
    Sync->>Audit: Log operation start
    Note over Audit: Record: user, operation, timestamp
    
    Sync->>DB: Read/Write operations
    
    alt Success
        DB-->>Sync: Operation complete
        Sync->>Audit: Log success + changes
    else Failure
        DB-->>Sync: Error
        Sync->>Audit: Log failure + reason
    end
    
    Sync-->>API: Return result
    API-->>U: Response
    
    Note over Audit: Audit trail maintained for compliance
```

## Implementation Priority

Based on the analysis of existing code and system requirements, here's the recommended implementation order:

1. **Phase 1: Foundation (Priority: Critical)**
   - Database schema migrations (new tables)
   - Basic staging and versioning models
   - Conflict detection logic

2. **Phase 2: Etilize Integration (Priority: High)**
   - Enhance existing FTP downloader
   - Integrate Xorosoft filtering
   - Implement staging workflow

3. **Phase 3: Shopify Sync (Priority: High)**
   - Sync down with versioning
   - Staged sync up workflow
   - Conflict resolution system

4. **Phase 4: UI Components (Priority: Medium)**
   - Sync dashboard
   - Staging review interface
   - Conflict resolution dialogs

5. **Phase 5: Optimization (Priority: Low)**
   - Performance tuning
   - Advanced caching
   - Monitoring dashboards

Each phase builds upon the previous one, allowing for incremental deployment and testing.