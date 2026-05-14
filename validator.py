import asyncio
import aiohttp
import time
import statistics
import json
from collections import defaultdict
from datetime import datetime

# ============================================
# ISP Scrubbing Validation Tool
# Authorized Use Only
# ============================================


def banner():
    print("""
====================================================
 ISP SCRUBBING VALIDATION TOOL
 Authorized Infrastructure Testing Only
====================================================
""")


async def worker(
    session, target, timeout_value, stop_time, worker_id,
    stats, latencies, stop_event=None
):
    while time.time() < stop_time:
        if stop_event and stop_event.is_set():
            break

        start = time.time()
        try:
            async with session.get(
                target,
                headers={
                    "User-Agent": "Authorized-ISP-Scrubbing-Validation",
                    "X-Test-Type": "ScrubbingVerification",
                    "X-Worker-ID": str(worker_id),
                },
                timeout=timeout_value,
            ) as response:
                latency = time.time() - start
                latencies.append(latency)
                if response.status < 500:
                    stats["success"] += 1
                else:
                    stats["server_errors"] += 1

        except asyncio.TimeoutError:
            stats["timeouts"] += 1

        except Exception:
            stats["connection_errors"] += 1


async def _live_reporter(stats, latencies, stop_time, stage_start, on_update, stop_event=None):
    await asyncio.sleep(2)
    while time.time() < stop_time:
        if stop_event and stop_event.is_set():
            break
        elapsed = time.time() - stage_start
        snapshot = compute_stats(dict(stats), list(latencies), elapsed)
        await on_update({"type": "stage_update", "data": snapshot})
        await asyncio.sleep(2)


async def run_stage(
    target, concurrent_users, duration, timeout_value,
    on_update=None, stop_event=None
):
    stats = defaultdict(int)
    latencies = []
    stage_start = time.time()
    stop_time = stage_start + duration

    connector = aiohttp.TCPConnector(limit=0, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            worker(session, target, timeout_value, stop_time, i,
                   stats, latencies, stop_event)
            for i in range(concurrent_users)
        ]
        if on_update:
            tasks.append(
                _live_reporter(stats, latencies, stop_time, stage_start,
                               on_update, stop_event)
            )
        await asyncio.gather(*tasks)

    elapsed = time.time() - stage_start
    return stats, latencies, elapsed


def compute_stats(stats, latencies, elapsed):
    total = (
        stats.get("success", 0)
        + stats.get("server_errors", 0)
        + stats.get("timeouts", 0)
        + stats.get("connection_errors", 0)
    )

    result = {
        "total_requests": total,
        "rps": round(total / elapsed, 2) if elapsed > 0 else 0.0,
        "success": stats.get("success", 0),
        "server_errors": stats.get("server_errors", 0),
        "timeouts": stats.get("timeouts", 0),
        "connection_errors": stats.get("connection_errors", 0),
        "avg_latency_s": None,
        "p95_latency_s": None,
        "p99_latency_s": None,
        "max_latency_s": None,
    }

    if latencies:
        s = sorted(latencies)
        n = len(s)
        result["avg_latency_s"] = round(statistics.mean(s), 3)
        result["max_latency_s"] = round(s[-1], 3)
        result["p95_latency_s"] = round(s[min(int(n * 0.95), n - 1)], 3)
        result["p99_latency_s"] = round(s[min(int(n * 0.99), n - 1)], 3)

    return result


def merge_stats(totals, stage_result):
    for key in ("total_requests", "success", "server_errors",
                "timeouts", "connection_errors"):
        totals[key] = totals.get(key, 0) + stage_result[key]


def print_stats(label, result):
    print(f"\n=== {label} ===")
    print(f"Total Requests      : {result['total_requests']}")
    print(f"Requests/sec (RPS)  : {result['rps']}")
    print(f"Successful          : {result['success']}")
    print(f"Server Errors       : {result['server_errors']}")
    print(f"Timeouts            : {result['timeouts']}")
    print(f"Connection Errors   : {result['connection_errors']}")
    if result["avg_latency_s"] is not None:
        print(f"Avg Latency         : {result['avg_latency_s']}s")
        print(f"p95 Latency         : {result['p95_latency_s']}s")
        print(f"p99 Latency         : {result['p99_latency_s']}s")
        print(f"Max Latency         : {result['max_latency_s']}s")


# ── Web API entry point ───────────────────────────────────────

async def run_test(config: dict, on_update=None, stop_event=None):
    target = config["target"]
    start_users = config["start_users"]
    ramp_step = config["ramp_step"]
    max_users = config["max_users"]
    stage_duration = config["stage_duration_s"]
    timeout_value = config["timeout_s"]
    cooldown = config["cooldown_s"]

    report_file = f"scrubbing_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report = {
        "config": config,
        "started_at": datetime.now().isoformat(),
        "stages": [],
        "final_totals": {},
    }

    cumulative = {}
    current_users = start_users

    while current_users <= max_users:
        if stop_event and stop_event.is_set():
            break

        if on_update:
            await on_update({
                "type": "log",
                "message": f"Stage starting — {current_users} concurrent users",
            })

        stage_stats, stage_latencies, elapsed = await run_stage(
            target, current_users, stage_duration,
            aiohttp.ClientTimeout(total=timeout_value),
            on_update=on_update,
            stop_event=stop_event,
        )

        result = compute_stats(stage_stats, stage_latencies, elapsed)
        result["concurrent_users"] = current_users
        result["duration_s"] = round(elapsed, 2)

        merge_stats(cumulative, result)
        report["stages"].append(result)

        if on_update:
            await on_update({
                "type": "stage_complete",
                "data": result,
                "cumulative": cumulative,
            })

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        if current_users + ramp_step <= max_users and not (
            stop_event and stop_event.is_set()
        ):
            if on_update:
                await on_update({
                    "type": "log",
                    "message": f"Cooling down for {cooldown}s...",
                })
            await asyncio.sleep(cooldown)

        current_users += ramp_step

    report["final_totals"] = cumulative
    report["completed_at"] = datetime.now().isoformat()

    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    if on_update:
        await on_update({
            "type": "test_complete",
            "report_file": report_file,
            "final": cumulative,
        })

    return report_file


# ── CLI entry point ───────────────────────────────────────────

def _get_int(prompt, min_val=1):
    while True:
        try:
            val = int(input(prompt).strip())
            if val < min_val:
                print(f"  Must be >= {min_val}. Try again.")
                continue
            return val
        except ValueError:
            print("  Enter a valid integer. Try again.")


def _get_url(prompt):
    while True:
        val = input(prompt).strip()
        if val.startswith("http://") or val.startswith("https://"):
            return val
        print("  URL must start with http:// or https://. Try again.")


async def cli_main():
    banner()

    target = _get_url("Target URL (https://example.com): ")
    start_users = _get_int("Initial concurrent users: ")
    ramp_step = _get_int("Ramp-up increment: ")
    max_users = _get_int(
        f"Maximum concurrent users (>= {start_users}): ", min_val=start_users
    )
    stage_duration = _get_int("Duration per stage (seconds): ")
    timeout_value = _get_int("HTTP timeout (seconds): ")
    cooldown = _get_int("Cooldown between stages (seconds): ", min_val=0)

    config = {
        "target": target,
        "start_users": start_users,
        "ramp_step": ramp_step,
        "max_users": max_users,
        "stage_duration_s": stage_duration,
        "timeout_s": timeout_value,
        "cooldown_s": cooldown,
    }

    print("\n===================================")
    print(" TEST CONFIGURATION")
    print("===================================")
    for k, v in config.items():
        print(f"{k:<22}: {v}")

    confirm = input("\nProceed with validation? (yes/no): ").lower()
    if confirm != "yes":
        print("\nAborted.")
        return

    stop_event = asyncio.Event()

    async def on_update(msg):
        if msg["type"] == "log":
            print(f"\n[>] {msg['message']}")
        elif msg["type"] == "stage_update":
            d = msg["data"]
            print(
                f"\r  Live — {d['total_requests']} reqs | {d['rps']} RPS",
                end="",
                flush=True,
            )
        elif msg["type"] == "stage_complete":
            print_stats("STAGE RESULTS", msg["data"])
        elif msg["type"] == "test_complete":
            print(f"\nReport saved → {msg['report_file']}")

    try:
        await run_test(config, on_update=on_update, stop_event=stop_event)
        print("\nValidation completed.")
    except KeyboardInterrupt:
        stop_event.set()
        print("\n\n[!] Interrupted — partial report saved.")


if __name__ == "__main__":
    asyncio.run(cli_main())
