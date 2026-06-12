# 🛡️ Homeschool Hero — Sentinel Analytics Rules

Microsoft Sentinel detection rules mapped to the [SecOps Squad security scan findings](https://github.com/x3nc0n/homeschool-hero/security/code-scanning) for Homeschool Hero.

## Deploy to Azure

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fx3nc0n%2Fhomeschool-hero%2Fmain%2Fsentinel%2Fazuredeploy.json)

> **Prerequisites:** A Log Analytics workspace with Microsoft Sentinel enabled.

### CLI Deployment

```bash
# Bicep (recommended)
az deployment group create \
  --resource-group <your-rg> \
  --template-file sentinel/main.bicep \
  --parameters workspaceName=<your-workspace>

# ARM JSON
az deployment group create \
  --resource-group <your-rg> \
  --template-file sentinel/azuredeploy.json \
  --parameters workspaceName=<your-workspace>
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `workspaceName` | string | *(required)* | Log Analytics workspace with Sentinel enabled |
| `enableRules` | bool | `true` | Deploy rules in enabled state; set `false` for review first |

---

## 📋 Rules Overview

| # | Rule Name | Severity | Finding(s) | MITRE ATT&CK | Data Source |
|---|-----------|----------|------------|---------------|-------------|
| 1 | **Upload Path Enumeration** | High | SAST-PYTHON-001 (9.5), DAST-CONFIG-001 | T1083, T1530 | `AppRequests` |
| 2 | **Default Credential Usage** | High | SAST-PYTHON-002, DAST-CONFIG-002 | T1078, T1110 | `AppRequests`, `AppTraces` |
| 3 | **Direct Database Access** | High | SAST-PYTHON-003 | T1210, T1552 | `CommonSecurityLog`, `ContainerLog` |
| 4 | **Demo Account Login** | Medium | SAST-PYTHON-004 | T1078.001 | `AppRequests`, `AppTraces` |
| 5 | **X-Forwarded-For Spoofing** | High | SAST-PYTHON-005 | T1110, T1090 | `AppRequests` |
| 6 | **Clickjacking / XSS Attempt** | Medium | SAST-NGINX-001 | T1189, T1059.007 | `AppRequests` |
| 7 | **Container Privilege Escalation** | High | SAST-DOCKER-003 | T1611, T1068 | `ContainerLog`, `Syslog` |
| 8 | **CI/CD Workflow Tampering** | High | SAST-CICD-001 | T1195.002 | `GitHubAuditData` |
| 9 | **Distributed Auth Brute Force** | Medium | SAST-PYTHON-005 + DAST-CONFIG-004/005 | T1110.003, T1110.004 | `AppRequests` |
| 10 | **Student Data Exfiltration** | High | SAST-PYTHON-001, SAST-PYTHON-009 | T1530, T1083 | `AppRequests` |

---

## 🔌 Required Data Connectors

Enable these Sentinel data connectors for full coverage:

| Connector | Required For Rules | Setup Guide |
|-----------|--------------------|-------------|
| **Application Insights** | 1, 2, 4, 5, 6, 9, 10 | [Docs](https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview) |
| **Common Event Format (CEF)** | 3 | [Docs](https://learn.microsoft.com/en-us/azure/sentinel/connect-common-event-format) |
| **Container Insights** | 3, 7 | [Docs](https://learn.microsoft.com/en-us/azure/azure-monitor/containers/container-insights-overview) |
| **Syslog** | 7 | [Docs](https://learn.microsoft.com/en-us/azure/sentinel/connect-syslog) |
| **GitHub (Audit Log)** | 8 | [Docs](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors/github) |

> **Tip:** If you use **nginx custom logs** instead of Application Insights, update the KQL queries to reference your custom log table (e.g., `NginxAccessLog_CL`) instead of `AppRequests`.

---

## 🗺️ Finding-to-Rule Mapping

```
SAST-PYTHON-001 (CVSS 9.5)  ──► Rule 1: Upload Enumeration
                              ──► Rule 10: Data Exfiltration

SAST-PYTHON-002 (CVSS 8.0)  ──► Rule 2: Default Credentials
DAST-CONFIG-002 (CVSS 8.0)  ──┘

SAST-PYTHON-003 (CVSS 8.0)  ──► Rule 3: Direct DB Access

SAST-PYTHON-004 (CVSS 8.0)  ──► Rule 4: Demo Account Login

SAST-PYTHON-005 (CVSS 8.0)  ──► Rule 5: IP Spoofing
                              ──► Rule 9: Distributed Brute Force

SAST-NGINX-001  (CVSS 8.0)  ──► Rule 6: Clickjacking / XSS

SAST-DOCKER-003 (CVSS 8.0)  ──► Rule 7: Container PrivEsc

SAST-CICD-001   (CVSS 8.0)  ──► Rule 8: CI/CD Tampering

DAST-CONFIG-001 (CVSS 8.0)  ──► Rule 1: Upload Enumeration (auth bypass)
```

---

## 📂 Files

```
sentinel/
├── main.bicep          # Bicep source (author/edit this)
├── azuredeploy.json    # Compiled ARM template (for Deploy to Azure button)
└── README.md           # This file
```

## Updating

After editing `main.bicep`, recompile the ARM template:

```bash
az bicep build --file sentinel/main.bicep --outfile sentinel/azuredeploy.json
```
