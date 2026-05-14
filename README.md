# ISP Scrubbing Validation Tool

A Python async load testing tool for validating ISP scrubbing center performance under controlled, authorized traffic ramp-up. Includes both a CLI mode and a browser-based live dashboard with real-time charts.

> **Authorized use only.** Run this tool only against infrastructure you own or have explicit written permission to test.

---

## Requirements

- Python 3.8+
- Ubuntu/Debian Linux (or any OS with Python 3)
- Root or sudo access (for system-level monitoring tools)

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

This installs system dependencies and creates an isolated Python virtual environment named `dos-sim` with all required packages inside it — no system Python packages are touched.

Installed:
- `python3`, `python3-pip`, `python3-venv`
- `htop`, `iftop`, `net-tools`, `curl` (for terminal monitoring)
- Python packages inside the venv: `aiohttp`, `fastapi`, `uvicorn`

---

## Permissions

This tool must only be used when:

- You **own** the target infrastructure, or
- You have **explicit written authorization** from the target owner

Every HTTP request includes the following headers to identify it as authorized testing traffic:

```
User-Agent: Authorized-ISP-Scrubbing-Validation
X-Test-Type: ScrubbingVerification
X-Worker-ID: <worker-number>
```

Unauthorized use against third-party systems is illegal and unethical.

---

## Running — Web Dashboard (recommended)

Launch the dashboard:

```bash
python3 start.py
```

The script automatically uses the virtual environment created by setup. It prints the URLs to open:

```
======================================================
  ISP SCRUBBING VALIDATOR
======================================================

  Dashboard URL:
    http://localhost:8000
    http://192.168.1.x:8000   <- share this with the client

  Press Ctrl+C to stop.
```

Then open the printed URL in your browser.

The dashboard provides:

- **Configuration form** — fill in all test parameters and click Start
- **Live KPI cards** — RPS, error rate, and p99 latency updating every 2 seconds during a stage
- **4 real-time charts** — updated after each stage completes:
  - Requests per second (RPS) per stage
  - Latency — avg, p95, p99 per stage
  - Concurrent users ramp
  - Request breakdown — success vs errors vs timeouts (stacked)
- **Live log panel** — timestamped stream of test events
- **Reports section** — lists all saved JSON reports with one-click download

The server streams updates over WebSocket. Multiple browser tabs can connect simultaneously and all receive the same live data. If the connection drops, the dashboard reconnects automatically.

To stop a running test, click **Stop** in the sidebar or press `Ctrl+C` in the terminal — a partial report is saved either way.

---

## Running — CLI Mode

```bash
python3 validator.py
```

The tool prompts for configuration interactively:

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

## CLI Example

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
target               : https://scrubbing.client-infra.com
start_users          : 50
ramp_step            : 50
max_users            : 200
stage_duration_s     : 30
timeout_s            : 10
cooldown_s           : 15

Proceed with validation? (yes/no): yes

[>] Stage starting — 50 concurrent users

  Live — 312 reqs | 52.0 RPS

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

[>] Cooling down for 15s...

[>] Stage starting — 100 concurrent users
...

Report saved → scrubbing_report_20260514_143022.json
```

---

## Report File

Each test run generates a timestamped JSON file in the working directory, e.g. `scrubbing_report_20260514_143022.json`. The file is written after every stage, so partial results are preserved if the test is interrupted.

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
  "final_totals": { "..." },
  "completed_at": "2026-05-14T14:35:47.813201"
}
```

Reports can be downloaded directly from the web dashboard's Reports section.

---

## Project Structure

```
dos-sim/
├── setup.py           # Bash setup script — creates venv + installs deps
├── start.py           # Start the dashboard (auto-uses venv, prints URL)
├── server.py          # FastAPI web server + WebSocket live update handler
├── validator.py       # Core async load testing engine + CLI entry point
├── requirements.txt   # Python dependencies
└── static/
    └── index.html     # Single-page web dashboard (Chart.js + Tailwind)
```

---

## Live Terminal Monitoring (during CLI mode)

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
| p95 / p99 latency | Real-world latency under load (more reliable than raw max) |
| Timeouts | Requests exceeding the HTTP timeout — scrubber may be dropping or delaying |
| Connection Errors | TCP-level failures — scrubber may be refusing connections at scale |
| Server Errors | HTTP 5xx responses — backend degrading under load |
