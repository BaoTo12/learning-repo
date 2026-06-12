#!/usr/bin/env python3
import os

modules_dir = r"c:\Users\Admin\Desktop\projects\learning-repo\mongodb-mastery\modules"

extra_sections = {
    "14-atlas-search-and-vector-search.md": """
---

## 15. Advanced Operational Diagnostic Playbook: Lucene Segment Merge & Disk Overhead

### 1. Lucene Segment Merge Process under the Hood
Atlas Search uses Lucene under the hood, which structures indexes into immutable segments. As database updates occur, new segments are written to disk. Periodically, Lucene runs background merge operations to combine small segments into larger ones. This process consumes significant system I/O and temporary disk space. If search nodes lack sufficient disk space, merge operations fail, segment counts spike, search query times degrade, and replication logs stall.

### 2. Operational Verification Commands
Verify search segment counts and monitor index size:
```javascript
// Query search status for index segments and sizes
db.products.aggregate([
  { $searchStatus: { showDetails: true } }
]);
```
Analyze the returned JSON payload. Pay close attention to:
*   `numSegments`: The number of search index segments. If this number is larger than 50, Lucene is falling behind on segment merge tasks.
*   `totalIndexSizeKB`: The size of the search index on disk. Ensure this value is below 60% of the allocated search node storage capacity to leave room for temporary merge operations.

### 3. Step-by-Step Resolution Runbook
1.  **Disable Dynamic Search Mappings**:
    Dynamic mapping indexes every field, creating a high volume of small, fragmented segments. Transition to explicit search mapping configurations.
2.  **Trigger Manual Segment Merges**:
    Scale search node compute tier temporarily to allocate higher I/O bandwidth, which speeds up background merge tasks.
3.  **Deploy Search Index Monitoring Alerting Rules**:
    Set up Prometheus alert thresholds for search disk utilization to trigger warnings when disk usage exceeds 75%.
""",
    "15-system-design-with-mongodb.md": """
---

## 15. Advanced Operational Diagnostic Playbook: Cold Storage Archiving with Atlas Data Federation

### 1. Cold Data Isolation and Tiering Strategy
For high-volume SaaS applications, keeping historical data in active collections slows down database queries and increases storage costs. A senior architect must implement a cold storage archiving policy. By transitioning records older than 90 days from primary replica nodes to AWS S3 buckets (cold storage), you keep active indexes small and memory-resident. You can use Atlas Data Federation to query active and archived collections simultaneously using unified aggregation queries.

### 2. Unified Query Implementation Script
Save the following aggregation query block as `federated-query.js`. It performs a unified query across the active MongoDB collection and the archived S3 files:
```javascript
// Perform a federated query across active database and S3 cold files
db.getSiblingDB("saas_db").transactions.aggregate([
  {
    $lookup: {
      from: "s3_archive_collection",
      localField: "tenantId",
      foreignField: "tenantId",
      as: "historicalRecords"
    }
  },
  {
    $project: {
      tenantId: 1,
      currentBalance: "$balance",
      archivedBalanceSum: { $sum: "$historicalRecords.amount" }
    }
  }
]);
```

### 3. Step-by-Step Resolution Runbook
1.  **Establish Data Federation Storage Mappings**:
    Define data stores in the Atlas Data Federation console, mapping active database collections and targets in the S3 bucket.
2.  **Configure Cold Storage Partitioning**:
    Ensure archived BSON files are structured in S3 using partitioned paths (e.g. `/year=YYYY/month=MM/tenantId=ID/`) to allow query engines to perform partition pruning.
3.  **Run Scheduled Retention Scripts**:
    Deploy background execution cron tasks to transfer data and verify delete completion logs regularly.
""",
    "11-application-integration.md": """
---

## 14. Advanced Operational Diagnostic Playbook: Serverless Connection Management in AWS Lambda

### 1. Connection Persistence in Stateless Run times
AWS Lambda runs code in ephemeral, stateless container instances. When a Lambda function handles an API request, it starts up, processes the event, and stands down. If the database client is initialized inside the request handler, every execution spawns a new connection. Under high traffic, this exhausts connection limits on the database server. To resolve this, instantiate the `MongoClient` outside the handler block. This allows the connection pool to persist across warm executions.

### 2. Code Implementation: Resilient Lambda Handler
Save the following Node.js code block as `lambda-handler.js` to reuse database client instances:
```javascript
const { MongoClient } = require('mongodb');

// Define connection parameters outside the handler scope
let cachedDb = null;
const uri = process.env.MONGODB_URI || "mongodb://localhost:27017/api_db";

async function connectToDatabase() {
  if (cachedDb) {
    return cachedDb;
  }
  
  console.log("No warm connection pool found. Creating new MongoClient instance...");
  const client = new MongoClient(uri, {
    maxPoolSize: 1, // Minimize pool size for serverless tasks
    connectTimeoutMS: 3000
  });
  
  await client.connect();
  cachedDb = client.db();
  return cachedDb;
}

exports.handler = async (event, context) => {
  // Allow Lambda to terminate immediately after event loop is empty
  context.callbackWaitsForEmptyEventLoop = false;
  
  const db = await connectToDatabase();
  const data = await db.collection("orders").find({ status: "PENDING" }).limit(10).toArray();
  
  return {
    statusCode: 200,
    body: JSON.stringify(data)
  };
};
```

### 3. Step-by-Step Resolution Runbook
1.  **Set `callbackWaitsForEmptyEventLoop` to False**:
    This forces the Lambda function to return responses immediately without waiting for background socket connections to close.
2.  **Minimize Driver Pool Limits**:
    Set `maxPoolSize` to 1 in serverless configurations to prevent database connection limits from being exhausted when Lambda functions scale horizontally.
3.  **Deploy Connection Proxy Layers**:
    Use proxy solutions (like AWS RDS Proxy or MongoDB Atlas App Services) to manage connection pooling between serverless clients and database nodes.
""",
    "13-testing-and-migrations.md": """
---

## 14. Advanced Operational Diagnostic Playbook: Pipeline CI/CD Data Migration Tests

### 1. Migration Testing in Automated Environments
To deploy schema changes without risks, you must automate migration tests in your CI/CD pipelines (e.g. Jenkins or GitHub Actions). The build step must deploy a local test replica set container, apply the migrations, verify database constraints, test the rollback paths, and clean up resources before production deployment.

### 2. Pipeline Configuration Block
Save the following configuration block as `.github/workflows/migration-test.yml` to define automated testing:
```yaml
name: Database Migration Test

on: [push]

jobs:
  test-migrations:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v3

      - name: Start MongoDB Test Container
        run: |
          docker run -d --name test-mongo -p 27017:27017 mongo:6.0.5

      - name: Set up JDK Environment
        uses: actions/setup-java@v3
        with:
          java-version: '17'
          distribution: 'temurin'

      - name: Run Schema Migration Tests
        run: |
          mvn clean test -Dtest=MigrationIntegrationTest -Dspring.profiles.active=test

      - name: Stop and Clean Test Containers
        run: |
          docker stop test-mongo
          docker rm test-mongo
```

### 3. Step-by-Step Resolution Runbook
1.  **Assert Clean States**:
    Configure test runners to deploy clean container volumes for each execution to ensure isolation.
2.  **Verify Rollback Scenarios**:
    Ensure the test suite runs the rollback steps and asserts that constraints return to previous states.
3.  **Integrate Audit Tracking**:
    Export test execution logs and store them in build artifacts for debugging purposes.
"""
}

def apply_extras():
    print("Applying Extra Operational Playbooks to module files...")
    
    for filename, section in extra_sections.items():
        filepath = os.path.join(modules_dir, filename)
        if not os.path.exists(filepath):
            print(f"Skipping {filename} - path not found.")
            continue
            
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        if "Lucene Segment Merge & Disk Overhead" in content or "Serverless Connection Management" in content or "Atlas Data Federation" in content or "CI/CD Data Migration Tests" in content:
            print(f"Skipping {filename} - already contains extra section.")
            continue
            
        # Append to the end of the file
        new_content = content.strip() + "\n\n" + section.strip() + "\n"
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print(f"Applied extra playbook to {filename} successfully.")

if __name__ == "__main__":
    apply_extras()
