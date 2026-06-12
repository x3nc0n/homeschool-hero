// ──────────────────────────────────────────────────────────────────────────────
// Homeschool Hero – Microsoft Sentinel Analytics Rules
// Detects exploitation attempts mapped to SecOps Squad security scan findings.
//
// Prerequisites:
//   1. A Log Analytics workspace with Microsoft Sentinel enabled.
//   2. Data connectors configured (see README.md for required connectors).
//
// Deploy:
//   az deployment group create \
//     --resource-group <rg> \
//     --template-file sentinel/main.bicep \
//     --parameters workspaceName=<workspace>
// ──────────────────────────────────────────────────────────────────────────────

@description('Name of the Log Analytics workspace with Microsoft Sentinel enabled.')
param workspaceName string

@description('Enable all analytics rules on deployment. Set to false to deploy in disabled state.')
param enableRules bool = true

// ── Existing workspace reference ────────────────────────────────────────────
resource workspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: workspaceName
}

// ═══════════════════════════════════════════════════════════════════════════════
// Rule 1 – Upload Path Enumeration / Unauthenticated Access
// Findings: SAST-PYTHON-001 (CVSS 9.5), DAST-CONFIG-001 (CVSS 8.0)
// CWE-284: Improper Access Control
// ═══════════════════════════════════════════════════════════════════════════════
resource ruleUploadEnum 'Microsoft.SecurityInsights/alertRules@2023-11-01' = {
  name: guid(subscription().subscriptionId, resourceGroup().id, 'hsh-upload-enum')
  scope: workspace
  kind: 'Scheduled'
  properties: {
    displayName: 'Homeschool Hero – Upload Path Enumeration (SAST-PYTHON-001)'
    description: '''The /uploads endpoint serves student files without authentication.
This rule detects enumeration or bulk access patterns against /uploads/ paths,
which may indicate an attacker harvesting student submissions, homework, or portfolio files.
Mapped to: SAST-PYTHON-001 (CVSS 9.5), DAST-CONFIG-001 (CVSS 8.0) | CWE-284'''
    severity: 'High'
    enabled: enableRules
    query: '''
// Detect high-volume requests to /uploads/ from a single source
let threshold = 20;
let timeWindow = 5m;
// AppRequests from Application Insights connector
AppRequests
| where TimeGenerated > ago(1h)
| where Url has "/uploads/"
| summarize
    RequestCount = count(),
    DistinctPaths = dcount(Url),
    Paths = make_set(Url, 25),
    FirstSeen = min(TimeGenerated),
    LastSeen = max(TimeGenerated)
  by ClientIP, bin(TimeGenerated, timeWindow)
| where RequestCount > threshold or DistinctPaths > 10
| extend
    AlertDetail = strcat("IP ", ClientIP, " made ", RequestCount,
                         " requests to ", DistinctPaths, " distinct /uploads/ paths in ", timeWindow)
| project TimeGenerated, ClientIP, RequestCount, DistinctPaths, Paths, FirstSeen, LastSeen, AlertDetail
'''
    queryFrequency: 'PT5M'
    queryPeriod: 'PT1H'
    triggerOperator: 'GreaterThan'
    triggerThreshold: 0
    suppressionDuration: 'PT1H'
    suppressionEnabled: false
    tactics: [
      'Collection'
      'Discovery'
    ]
    techniques: [
      'T1083'
      'T1530'
    ]
    entityMappings: [
      {
        entityType: 'IP'
        fieldMappings: [
          {
            identifier: 'Address'
            columnName: 'ClientIP'
          }
        ]
      }
    ]
    customDetails: {
      RequestCount: 'RequestCount'
      DistinctPaths: 'DistinctPaths'
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Rule 2 – Default Credential Login Attempts
// Findings: SAST-PYTHON-002 (CVSS 8.0), DAST-CONFIG-002 (CVSS 8.0)
// CWE-798: Use of Hard-coded Credentials
// ═══════════════════════════════════════════════════════════════════════════════
resource ruleDefaultCreds 'Microsoft.SecurityInsights/alertRules@2023-11-01' = {
  name: guid(subscription().subscriptionId, resourceGroup().id, 'hsh-default-creds')
  scope: workspace
  kind: 'Scheduled'
  properties: {
    displayName: 'Homeschool Hero – Default Credential Usage (SAST-PYTHON-002)'
    description: '''POSTGRES_PASSWORD and FAMILY_PASSWORD default to "changeme" with no startup
enforcement. This rule detects authentication activity associated with known default
credentials or well-known weak passwords targeting the application.
Mapped to: SAST-PYTHON-002, DAST-CONFIG-002 (CVSS 8.0) | CWE-798'''
    severity: 'High'
    enabled: enableRules
    query: '''
// Detect auth requests that may use default/weak credentials
// Looks for login attempts followed by immediate success (credential stuffing with defaults)
let knownDefaults = dynamic(["changeme", "dev-secret-change-me", "demo1234"]);
// Application traces from the auth module
AppTraces
| where TimeGenerated > ago(1h)
| where Message has_any ("login", "authenticate", "sign_in", "family_password")
| where Message has_any (knownDefaults)
    or Message has "default password"
    or Message has "FAMILY_PASSWORD"
| summarize
    AttemptCount = count(),
    Messages = make_set(Message, 10)
  by ClientIP, bin(TimeGenerated, 5m)
| project TimeGenerated, ClientIP, AttemptCount, Messages
// Also check for successful auth from bootstrap/default owner email
| union (
  AppRequests
  | where TimeGenerated > ago(1h)
  | where Url has "/api/auth/login"
  | where ResultCode == 200
  | join kind=inner (
      AppTraces
      | where TimeGenerated > ago(1h)
      | where Message has "owner@homeschool-hero.local"
  ) on ClientIP
  | project TimeGenerated, ClientIP, AttemptCount = 1, Messages = pack_array("Login with default owner email")
)
'''
    queryFrequency: 'PT10M'
    queryPeriod: 'PT1H'
    triggerOperator: 'GreaterThan'
    triggerThreshold: 0
    suppressionDuration: 'PT1H'
    suppressionEnabled: false
    tactics: [
      'InitialAccess'
      'CredentialAccess'
    ]
    techniques: [
      'T1078'
      'T1110'
    ]
    entityMappings: [
      {
        entityType: 'IP'
        fieldMappings: [
          {
            identifier: 'Address'
            columnName: 'ClientIP'
          }
        ]
      }
    ]
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Rule 3 – Direct Database Access with Hardcoded Credentials
// Finding: SAST-PYTHON-003 (CVSS 8.0)
// CWE-312: Cleartext Storage of Sensitive Information
// ═══════════════════════════════════════════════════════════════════════════════
resource ruleDbDirectAccess 'Microsoft.SecurityInsights/alertRules@2023-11-01' = {
  name: guid(subscription().subscriptionId, resourceGroup().id, 'hsh-db-direct-access')
  scope: workspace
  kind: 'Scheduled'
  properties: {
    displayName: 'Homeschool Hero – Direct Database Access Attempt (SAST-PYTHON-003)'
    description: '''alembic.ini contains hardcoded PostgreSQL credentials. This rule detects
direct connection attempts to the PostgreSQL service from unexpected sources,
indicating potential exploitation of leaked credentials.
Mapped to: SAST-PYTHON-003 (CVSS 8.0) | CWE-312'''
    severity: 'High'
    enabled: enableRules
    query: '''
// Detect connections to PostgreSQL port (5432) from non-application sources
let allowedSources = dynamic(["backend", "alembic", "10.0.0.0/8"]);
// Network flow logs or firewall logs
CommonSecurityLog
| where TimeGenerated > ago(1h)
| where DestinationPort == 5432
| where DeviceAction != "Deny"
| where not(SourceIP matches regex @"^10\.\d+\.\d+\.\d+$")
| where not(SourceIP matches regex @"^172\.(1[6-9]|2\d|3[01])\.\d+\.\d+$")
| summarize
    ConnectionCount = count(),
    SourceIPs = make_set(SourceIP, 10),
    FirstSeen = min(TimeGenerated),
    LastSeen = max(TimeGenerated)
  by DestinationIP, DestinationPort, bin(TimeGenerated, 5m)
| where ConnectionCount > 0
| project TimeGenerated, DestinationIP, DestinationPort, ConnectionCount, SourceIPs, FirstSeen, LastSeen
// Also check container logs for unexpected psql connections
| union (
  ContainerLog
  | where TimeGenerated > ago(1h)
  | where LogEntry has "postgresql" and LogEntry has_any ("connection received", "password authentication")
  | where LogEntry !has "backend"
  | project TimeGenerated, DestinationIP = "", DestinationPort = 5432,
            ConnectionCount = 1, SourceIPs = dynamic([""]),
            FirstSeen = TimeGenerated, LastSeen = TimeGenerated
)
'''
    queryFrequency: 'PT5M'
    queryPeriod: 'PT1H'
    triggerOperator: 'GreaterThan'
    triggerThreshold: 0
    suppressionDuration: 'PT1H'
    suppressionEnabled: false
    tactics: [
      'LateralMovement'
      'CredentialAccess'
    ]
    techniques: [
      'T1210'
      'T1552'
    ]
    entityMappings: [
      {
        entityType: 'IP'
        fieldMappings: [
          {
            identifier: 'Address'
            columnName: 'DestinationIP'
          }
        ]
      }
    ]
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Rule 4 – Demo Account Exploitation
// Finding: SAST-PYTHON-004 (CVSS 8.0)
// CWE-521: Weak Password Requirements
// ═══════════════════════════════════════════════════════════════════════════════
resource ruleDemoAccount 'Microsoft.SecurityInsights/alertRules@2023-11-01' = {
  name: guid(subscription().subscriptionId, resourceGroup().id, 'hsh-demo-account')
  scope: workspace
  kind: 'Scheduled'
  properties: {
    displayName: 'Homeschool Hero – Demo Account Login in Production (SAST-PYTHON-004)'
    description: '''Demo accounts are seeded with password "demo1234" which bypasses the app password
policy. This rule fires when demo/seed accounts are used for authentication,
especially in non-demo environments — indicating credential stuffing or reuse.
Mapped to: SAST-PYTHON-004 (CVSS 8.0) | CWE-521'''
    severity: 'Medium'
    enabled: enableRules
    query: '''
// Detect logins using demo/seed accounts
let demoIndicators = dynamic(["demo", "seed", "test_family", "demo_student"]);
AppRequests
| where TimeGenerated > ago(1h)
| where Url has "/api/auth/login"
| where ResultCode in (200, 401, 403)
| join kind=inner (
    AppTraces
    | where TimeGenerated > ago(1h)
    | where Message has_any (demoIndicators)
    | where Message has_any ("login", "authenticate", "session")
) on OperationId
| summarize
    LoginAttempts = count(),
    SuccessCount = countif(ResultCode == 200),
    FailCount = countif(ResultCode != 200),
    DistinctIPs = dcount(ClientIP)
  by ClientIP, bin(TimeGenerated, 15m)
| project TimeGenerated, ClientIP, LoginAttempts, SuccessCount, FailCount, DistinctIPs
'''
    queryFrequency: 'PT15M'
    queryPeriod: 'PT1H'
    triggerOperator: 'GreaterThan'
    triggerThreshold: 0
    suppressionDuration: 'PT1H'
    suppressionEnabled: false
    tactics: [
      'InitialAccess'
    ]
    techniques: [
      'T1078.001'
    ]
    entityMappings: [
      {
        entityType: 'IP'
        fieldMappings: [
          {
            identifier: 'Address'
            columnName: 'ClientIP'
          }
        ]
      }
    ]
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Rule 5 – X-Forwarded-For IP Spoofing / Rate Limit Bypass
// Finding: SAST-PYTHON-005 (CVSS 8.0)
// CWE-348: Use of Less Trusted Source
// ═══════════════════════════════════════════════════════════════════════════════
resource ruleIpSpoof 'Microsoft.SecurityInsights/alertRules@2023-11-01' = {
  name: guid(subscription().subscriptionId, resourceGroup().id, 'hsh-ip-spoof')
  scope: workspace
  kind: 'Scheduled'
  properties: {
    displayName: 'Homeschool Hero – X-Forwarded-For Spoofing / Rate Limit Bypass (SAST-PYTHON-005)'
    description: '''The rate limiter trusts X-Forwarded-For without validation. This rule detects
patterns where a single source IP rotates through many X-Forwarded-For values
to bypass rate limiting on auth endpoints, or where auth failures exceed the
configured limit (5/60s) suggesting successful bypass.
Mapped to: SAST-PYTHON-005 (CVSS 8.0) | CWE-348'''
    severity: 'High'
    enabled: enableRules
    query: '''
// Detect auth brute-force that exceeds the app rate limit (5 req/60s)
// If an IP sends >5 failed logins per minute, the rate limiter was bypassed
let authRateLimit = 5;
AppRequests
| where TimeGenerated > ago(1h)
| where Url has_any ("/api/auth/login", "/api/auth/family")
| where ResultCode in (401, 403, 429)
| summarize
    FailedAttempts = count(),
    DistinctUrls = dcount(Url),
    FirstSeen = min(TimeGenerated),
    LastSeen = max(TimeGenerated)
  by ClientIP, bin(TimeGenerated, 1m)
| where FailedAttempts > authRateLimit
| extend
    BypassIndicator = iff(FailedAttempts > authRateLimit * 2,
                          "Strong indicator of rate limit bypass via X-Forwarded-For spoofing",
                          "Possible rate limit bypass")
| project TimeGenerated, ClientIP, FailedAttempts, DistinctUrls, FirstSeen, LastSeen, BypassIndicator
'''
    queryFrequency: 'PT5M'
    queryPeriod: 'PT1H'
    triggerOperator: 'GreaterThan'
    triggerThreshold: 0
    suppressionDuration: 'PT1H'
    suppressionEnabled: false
    tactics: [
      'CredentialAccess'
      'DefenseEvasion'
    ]
    techniques: [
      'T1110'
      'T1090'
    ]
    entityMappings: [
      {
        entityType: 'IP'
        fieldMappings: [
          {
            identifier: 'Address'
            columnName: 'ClientIP'
          }
        ]
      }
    ]
    customDetails: {
      FailedAttempts: 'FailedAttempts'
      BypassIndicator: 'BypassIndicator'
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Rule 6 – Missing Security Headers Exploitation
// Finding: SAST-NGINX-001 (CVSS 8.0)
// CWE-693: Protection Mechanism Failure
// ═══════════════════════════════════════════════════════════════════════════════
resource ruleMissingHeaders 'Microsoft.SecurityInsights/alertRules@2023-11-01' = {
  name: guid(subscription().subscriptionId, resourceGroup().id, 'hsh-clickjack-xss')
  scope: workspace
  kind: 'Scheduled'
  properties: {
    displayName: 'Homeschool Hero – Clickjacking / XSS Attempt (SAST-NGINX-001)'
    description: '''Nginx is missing CSP, X-Frame-Options, and X-Content-Type-Options headers.
This rule detects potential exploitation via iframe embedding (clickjacking)
or cross-site scripting payloads targeting the unprotected application.
Mapped to: SAST-NGINX-001 (CVSS 8.0) | CWE-693'''
    severity: 'Medium'
    enabled: enableRules
    query: '''
// Detect XSS/clickjacking exploitation attempts
let xssPatterns = dynamic(["<script", "javascript:", "onerror=", "onload=",
                           "eval(", "document.cookie", "alert(", "String.fromCharCode"]);
let iframePatterns = dynamic(["<iframe", "<frame", "<object", "<embed"]);
AppRequests
| where TimeGenerated > ago(1h)
| where Url has_any (xssPatterns) or Name has_any (xssPatterns)
| summarize
    XSSAttempts = count(),
    Payloads = make_set(Url, 20),
    DistinctPaths = dcount(Url)
  by ClientIP, bin(TimeGenerated, 5m)
| project TimeGenerated, ClientIP, XSSAttempts, DistinctPaths, Payloads,
          AttackType = "XSS Attempt (no CSP protection)"
| union (
  // Detect Referer headers from external sites embedding this app (clickjacking)
  AppRequests
  | where TimeGenerated > ago(1h)
  | extend Referer = tostring(Properties["Referer"])
  | where isnotempty(Referer)
  | where Referer !has "homeschool-hero" and Referer !has "localhost"
  | where Url has "/api/auth" or Url has "/api/family"
  | summarize
      EmbedAttempts = count(),
      Referers = make_set(Referer, 10)
    by ClientIP, bin(TimeGenerated, 15m)
  | where EmbedAttempts > 3
  | project TimeGenerated, ClientIP, XSSAttempts = EmbedAttempts,
            DistinctPaths = 0, Payloads = Referers,
            AttackType = "Clickjacking (no X-Frame-Options)"
)
'''
    queryFrequency: 'PT5M'
    queryPeriod: 'PT1H'
    triggerOperator: 'GreaterThan'
    triggerThreshold: 0
    suppressionDuration: 'PT1H'
    suppressionEnabled: false
    tactics: [
      'InitialAccess'
      'Execution'
    ]
    techniques: [
      'T1189'
      'T1059.007'
    ]
    entityMappings: [
      {
        entityType: 'IP'
        fieldMappings: [
          {
            identifier: 'Address'
            columnName: 'ClientIP'
          }
        ]
      }
    ]
    customDetails: {
      AttackType: 'AttackType'
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Rule 7 – Container Privilege Escalation
// Finding: SAST-DOCKER-003 (CVSS 8.0)
// CWE-250: Execution with Unnecessary Privileges
// ═══════════════════════════════════════════════════════════════════════════════
resource ruleContainerEscape 'Microsoft.SecurityInsights/alertRules@2023-11-01' = {
  name: guid(subscription().subscriptionId, resourceGroup().id, 'hsh-container-privesc')
  scope: workspace
  kind: 'Scheduled'
  properties: {
    displayName: 'Homeschool Hero – Container Privilege Escalation (SAST-DOCKER-003)'
    description: '''The nginx container lacks "no-new-privileges" and "cap_drop: ALL" hardening.
This rule detects privilege escalation, capability acquisition, or escape attempts
from the container runtime environment.
Mapped to: SAST-DOCKER-003 (CVSS 8.0) | CWE-250'''
    severity: 'High'
    enabled: enableRules
    query: '''
// Detect privilege escalation or suspicious commands inside containers
let privescIndicators = dynamic(["setuid", "setgid", "cap_add", "nsenter",
    "mount", "chroot", "/proc/self", "/proc/1", "docker.sock",
    "SYS_ADMIN", "SYS_PTRACE", "NET_RAW", "CAP_"]);
ContainerLog
| where TimeGenerated > ago(1h)
| where ContainerID has_any ("nginx", "homeschool")
| where LogEntry has_any (privescIndicators)
| summarize
    EventCount = count(),
    Entries = make_set(LogEntry, 15),
    Containers = make_set(ContainerID, 5)
  by Computer, bin(TimeGenerated, 5m)
| project TimeGenerated, Computer, EventCount, Containers, Entries
| union (
  // Syslog-based detection for container escape via kernel exploits
  Syslog
  | where TimeGenerated > ago(1h)
  | where SyslogMessage has_any ("container", "docker", "runc")
  | where SyslogMessage has_any ("escape", "breakout", "privilege", "exploit", "capability")
  | project TimeGenerated, Computer, EventCount = 1,
            Containers = dynamic([""]),
            Entries = pack_array(SyslogMessage)
)
'''
    queryFrequency: 'PT5M'
    queryPeriod: 'PT1H'
    triggerOperator: 'GreaterThan'
    triggerThreshold: 0
    suppressionDuration: 'PT1H'
    suppressionEnabled: false
    tactics: [
      'PrivilegeEscalation'
      'Execution'
    ]
    techniques: [
      'T1611'
      'T1068'
    ]
    entityMappings: [
      {
        entityType: 'Host'
        fieldMappings: [
          {
            identifier: 'HostName'
            columnName: 'Computer'
          }
        ]
      }
    ]
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Rule 8 – CI/CD Supply Chain Tampering
// Finding: SAST-CICD-001 (CVSS 8.0)
// CWE-829: Inclusion of Functionality from Untrusted Control Sphere
// ═══════════════════════════════════════════════════════════════════════════════
resource ruleCicdTamper 'Microsoft.SecurityInsights/alertRules@2023-11-01' = {
  name: guid(subscription().subscriptionId, resourceGroup().id, 'hsh-cicd-tamper')
  scope: workspace
  kind: 'Scheduled'
  properties: {
    displayName: 'Homeschool Hero – CI/CD Workflow Tampering (SAST-CICD-001)'
    description: '''Third-party GitHub Actions are referenced by mutable tags, not pinned SHAs.
This rule detects modifications to workflow files, unexpected workflow runs, or
changes to Actions referenced in the pipeline — potential supply chain attacks.
Mapped to: SAST-CICD-001 (CVSS 8.0) | CWE-829'''
    severity: 'High'
    enabled: enableRules
    query: '''
// Detect modifications to GitHub Actions workflow files
// Requires: GitHub Audit Log connector or GitHubAuditLogPolling data connector
let workflowPaths = dynamic([".github/workflows/ci.yml", ".github/workflows/release.yml",
    ".github/workflows/squad-auto-patch.yml"]);
// GitHub audit log events for push/commit to workflow files
GitHubAuditData
| where TimeGenerated > ago(1h)
| where Action in ("git.push", "workflows.completed_workflow_run", "repo.edit")
| where RawEventData has ".github/workflows"
| extend
    Actor = tostring(RawEventData.actor),
    Repo = tostring(RawEventData.repo),
    ModifiedFiles = tostring(RawEventData.modified_files)
| where ModifiedFiles has_any (workflowPaths) or RawEventData has "workflow"
| summarize
    ChangeCount = count(),
    Actors = make_set(Actor, 10),
    Actions = make_set(Action, 5)
  by Repo, bin(TimeGenerated, 1h)
| project TimeGenerated, Repo, ChangeCount, Actors, Actions,
          RiskNote = "Unpinned Actions are vulnerable to tag hijacking — verify commit SHAs"
'''
    queryFrequency: 'PT1H'
    queryPeriod: 'PT24H'
    triggerOperator: 'GreaterThan'
    triggerThreshold: 0
    suppressionDuration: 'PT1H'
    suppressionEnabled: false
    tactics: [
      'InitialAccess'
      'Execution'
    ]
    techniques: [
      'T1195.002'
    ]
    entityMappings: [
      {
        entityType: 'Account'
        fieldMappings: [
          {
            identifier: 'Name'
            columnName: 'Repo'
          }
        ]
      }
    ]
    customDetails: {
      Actors: 'Actors'
      RiskNote: 'RiskNote'
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Rule 9 – Auth Brute Force (Distributed)
// Findings: SAST-PYTHON-005 (rate limiter bypass), DAST-CONFIG-004/005
// CWE-307: Improper Restriction of Excessive Authentication Attempts
// ═══════════════════════════════════════════════════════════════════════════════
resource ruleBruteForce 'Microsoft.SecurityInsights/alertRules@2023-11-01' = {
  name: guid(subscription().subscriptionId, resourceGroup().id, 'hsh-brute-force')
  scope: workspace
  kind: 'Scheduled'
  properties: {
    displayName: 'Homeschool Hero – Distributed Auth Brute Force (SAST-PYTHON-005)'
    description: '''The in-memory rate limiter resets on restart and is per-worker only.
This rule detects distributed brute-force attacks where multiple IPs target
the same auth endpoints — an attack pattern the app rate limiter cannot stop.
Mapped to: SAST-PYTHON-005 + DAST-CONFIG-004/005 | CWE-307'''
    severity: 'Medium'
    enabled: enableRules
    query: '''
// Distributed brute-force: many IPs hitting auth endpoints with high failure rate
AppRequests
| where TimeGenerated > ago(1h)
| where Url has_any ("/api/auth/login", "/api/auth/family", "/api/auth/register")
| where ResultCode in (401, 403, 422)
| summarize
    TotalFailures = count(),
    DistinctIPs = dcount(ClientIP),
    IPs = make_set(ClientIP, 50),
    TargetedEndpoints = make_set(Url, 5)
  by bin(TimeGenerated, 10m)
| where TotalFailures > 30 and DistinctIPs > 5
| extend Severity = iff(DistinctIPs > 20, "Critical — large-scale distributed attack",
                        "High — multi-source brute force")
| project TimeGenerated, TotalFailures, DistinctIPs, IPs, TargetedEndpoints, Severity
'''
    queryFrequency: 'PT10M'
    queryPeriod: 'PT1H'
    triggerOperator: 'GreaterThan'
    triggerThreshold: 0
    suppressionDuration: 'PT1H'
    suppressionEnabled: false
    tactics: [
      'CredentialAccess'
    ]
    techniques: [
      'T1110.003'
      'T1110.004'
    ]
    customDetails: {
      TotalFailures: 'TotalFailures'
      DistinctIPs: 'DistinctIPs'
      Severity: 'Severity'
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Rule 10 – Sensitive Student Data Exfiltration via Uploads
// Findings: SAST-PYTHON-001 (uploads unauthenticated), SAST-PYTHON-009 (path traversal)
// CWE-200: Exposure of Sensitive Information
// ═══════════════════════════════════════════════════════════════════════════════
resource ruleDataExfil 'Microsoft.SecurityInsights/alertRules@2023-11-01' = {
  name: guid(subscription().subscriptionId, resourceGroup().id, 'hsh-data-exfil')
  scope: workspace
  kind: 'Scheduled'
  properties: {
    displayName: 'Homeschool Hero – Student Data Exfiltration via Uploads (SAST-PYTHON-001)'
    description: '''With unauthenticated uploads and potential path traversal, an attacker can
bulk-download student submissions, OCR documents, and portfolio files. This rule
detects high-volume successful downloads or path traversal attempts against /uploads/.
Mapped to: SAST-PYTHON-001 (CVSS 9.5), SAST-PYTHON-009 (CVSS 5.5) | CWE-200'''
    severity: 'High'
    enabled: enableRules
    query: '''
// Bulk download or path traversal against /uploads/
let traversalPatterns = dynamic(["../", "..%2f", "..%5c", "%2e%2e", "..\\",
    "/etc/passwd", "/proc/self"]);
AppRequests
| where TimeGenerated > ago(1h)
| where Url has "/uploads/"
| where ResultCode == 200
| summarize
    SuccessfulDownloads = count(),
    TotalBytes = sum(toint(Properties["ResponseSize"])),
    DistinctFiles = dcount(Url),
    SamplePaths = make_set(Url, 20)
  by ClientIP, bin(TimeGenerated, 15m)
| where SuccessfulDownloads > 15 or DistinctFiles > 10
| extend ExfilMB = round(TotalBytes / 1048576.0, 2)
| project TimeGenerated, ClientIP, SuccessfulDownloads, DistinctFiles, ExfilMB, SamplePaths,
          AlertType = "Bulk data exfiltration via unauthenticated /uploads/"
| union (
  // Path traversal attempts
  AppRequests
  | where TimeGenerated > ago(1h)
  | where Url has "/uploads/" and Url has_any (traversalPatterns)
  | summarize
      TraversalAttempts = count(),
      Payloads = make_set(Url, 20)
    by ClientIP, bin(TimeGenerated, 5m)
  | project TimeGenerated, ClientIP, SuccessfulDownloads = TraversalAttempts,
            DistinctFiles = 0, ExfilMB = 0.0, SamplePaths = Payloads,
            AlertType = "Path traversal attempt against /uploads/"
)
'''
    queryFrequency: 'PT10M'
    queryPeriod: 'PT1H'
    triggerOperator: 'GreaterThan'
    triggerThreshold: 0
    suppressionDuration: 'PT1H'
    suppressionEnabled: false
    tactics: [
      'Exfiltration'
      'Collection'
    ]
    techniques: [
      'T1530'
      'T1083'
    ]
    entityMappings: [
      {
        entityType: 'IP'
        fieldMappings: [
          {
            identifier: 'Address'
            columnName: 'ClientIP'
          }
        ]
      }
    ]
    customDetails: {
      AlertType: 'AlertType'
      ExfilMB: 'ExfilMB'
      SuccessfulDownloads: 'SuccessfulDownloads'
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Outputs
// ═══════════════════════════════════════════════════════════════════════════════
output deployedRules array = [
  ruleUploadEnum.id
  ruleDefaultCreds.id
  ruleDbDirectAccess.id
  ruleDemoAccount.id
  ruleIpSpoof.id
  ruleMissingHeaders.id
  ruleContainerEscape.id
  ruleCicdTamper.id
  ruleBruteForce.id
  ruleDataExfil.id
]

output ruleCount int = 10
