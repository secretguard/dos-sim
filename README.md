# ISP Scrubbing Validation Tool

A Python async load testing tool for validating ISP scrubbing center performance under controlled, authorized traffic ramp-up.

> **Authorized use only.** Run this tool only against infrastructure you own or have explicit written permission to test.

---

## Requirements

- Python 3.8+
- Ubuntu/Debian Linux (or any OS with Python 3)
- Root or sudo access (for monitoring tools)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/secretguard/dos-sim.git
cd dos-sim
```

### 2. Run the setup script

```bash
chmod +x setup.py
sudo bash setup.py
```

This installs:
- `python3`, `python3-pip`
- `htop`, `iftop`, `net-tools`, `curl` (for live monitoring)
- `aiohttp` Python package

### 3. Manual install (alternative)

```bash
pip3 install -r requirements.txt
```

---

## Permissions

This tool must only be used when:

- You **own** the target infrastructure, or
- You have **explicit written authorization** from the target owner

Every HTTP request sent by this tool includes the following headers to identify it as authorized testing traffic:

```
User-Agent: Authorized-ISP-Scrubbing-Validation
X-Test-Type: ScrubbingVerification
X-Worker-ID: <worker-number>
```

Unauthorized use against third-party systems is illegal and unethical.

---

## First Run

```bash
python3 validator.py
```

The tool will prompt you for configuration interactively:

| Prompt | Description |
|---|---|
| Target URL | Full URL including scheme, e.g. `https://target.example.com` |
| Initial concurrent users | Number of workers to start with |
| Ramp-up increment | Workers added after each stage |
| Maximum concurrent users | Cap — test stops when this is reached |
| Duration per stage (seconds) | How long each load level runs |
| HTTP timeout (seconds) | Per-request timeout before marking as timed out |
| Cooldown between stages (seconds) | Pause between stages to let the target recover |

After entering values you will see a configuration summary and must type `yes` to confirm before the test starts.

---

## Example

```
====================================================
 ISP SCRUBBING VALIDATION TOOL
 Authorized Infrastructure Testing Only
====================================================

Target URL (https://example.com): https://scrubbing.client-infra.com
Initial concurrent users: 50
Ramp-up increment: 50
Maximum concurrent users: 200
Duration per stage (seconds): 30
HTTP timeout (seconds): 10
Cooldown between stages (seconds): 15

===================================
 TEST CONFIGURATION
===================================
Target               : https://scrubbing.client-infra.com
Initial Users        : 50
Ramp Increment       : 50
Maximum Users        : 200
Stage Duration       : 30s
Timeout              : 10s
Cooldown             : 15s

Proceed with validation? (yes/no): yes

===================================
 RUNNING STAGE: 50 CONCURRENT USERS
===================================

Stage completed in 30.04s

=== STAGE RESULTS ===
Total Requests      : 4821
Requests/sec (RPS)  : 160.49
Successful          : 4810
Server Errors       : 3
Timeouts            : 7
Connection Errors   : 1
Avg Latency         : 0.308s
p95 Latency         : 0.741s
p99 Latency         : 1.102s
Max Latency         : 2.317s

Cooling down for 15 seconds...

===================================
 RUNNING STAGE: 100 CONCURRENT USERS
===================================
...
```

At the end of the test (or on `Ctrl+C`), a full JSON report is saved:

```
Report saved → scrubbing_report_20260514_143022.json
```

---

## Report File

Each test run generates a timestamped JSON file in the working directory, e.g. `scrubbing_report_20260514_143022.json`.

```json
{
  "config": {
    "target": "https://scrubbing.client-infra.com",
    "start_users": 50,
    "ramp_step": 50,
    "max_users": 200,
    "stage_duration_s": 30,
    "timeout_s": 10,
    "cooldown_s": 15
  },
  "started_at": "2026-05-14T14:30:22.410312",
  "stages": [
    {
      "concurrent_users": 50,
      "duration_s": 30.04,
      "total_requests": 4821,
      "rps": 160.49,
      "success": 4810,
      "server_errors": 3,
      "timeouts": 7,
      "connection_errors": 1,
      "avg_latency_s": 0.308,
      "p95_latency_s": 0.741,
      "p99_latency_s": 1.102,
      "max_latency_s": 2.317
    }
  ],
  "final_totals": { ... },
  "completed_at": "2026-05-14T14:35:47.813201"
}
```

The report is written after every stage, so partial results are preserved if the test is interrupted.

---

## Live Monitoring (during test)

Open a second terminal and use:

```bash
htop                    # CPU and memory per process
sudo iftop              # Live network bandwidth
ss -s                   # Socket summary
netstat -ant | wc -l    # Total active connections
```

---

## Metrics Reference

| Metric | What it tells you |
|---|---|
| RPS | Throughput — whether the scrubbing center is throttling traffic |
| p95 / p99 latency | Real-world latency under load (more reliable than max) |
| Timeouts | Requests that exceeded the HTTP timeout — scrubber may be dropping or delaying |
| Connection Errors | TCP-level failures — scrubber may be refusing connections |
| Server Errors | HTTP 5xx responses — backend is degrading under load |
