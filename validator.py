import asyncio
import aiohttp
import time
import statistics
import json
import sys
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
    session,
    target,
    timeout_value,
    stop_time,
    worker_id,
    stats,
    latencies
):
    while time.time() < stop_time:

        start = time.time()

        try:
            async with session.get(
                target,
                headers={
                    "User-Agent":
                        "Authorized-ISP-Scrubbing-Validation",
                    "X-Test-Type":
                        "ScrubbingVerification",
                    "X-Worker-ID":
                        str(worker_id)
                },
                timeout=timeout_value
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


async def run_stage(
    target,
    concurrent_users,
    duration,
    timeout_value
):
    stats = defaultdict(int)
    latencies = []

    stop_time = time.time() + duration

    connector = aiohttp.TCPConnector(
        limit=0,
        ssl=False
    )

    async with aiohttp.ClientSession(
        connector=connector
    ) as session:

        tasks = [
            worker(
                session,
                target,
                timeout_value,
                stop_time,
                i,
                stats,
                latencies
            )
            for i in range(concurrent_users)
        ]

        await asyncio.gather(*tasks)

    return stats, latencies


def compute_stats(stats, latencies, elapsed):
    total = (
        stats["success"]
        + stats["server_errors"]
        + stats["timeouts"]
        + stats["connection_errors"]
    )

    rps = total / elapsed if elapsed > 0 else 0.0

    result = {
        "total_requests": total,
        "rps": round(rps, 2),
        "success": stats["success"],
        "server_errors": stats["server_errors"],
        "timeouts": stats["timeouts"],
        "connection_errors": stats["connection_errors"],
        "avg_latency_s": None,
        "p95_latency_s": None,
        "p99_latency_s": None,
        "max_latency_s": None,
    }

    if latencies:
        sorted_lat = sorted(latencies)
        n = len(sorted_lat)
        result["avg_latency_s"] = round(statistics.mean(sorted_lat), 3)
        result["max_latency_s"] = round(sorted_lat[-1], 3)
        result["p95_latency_s"] = round(
            sorted_lat[min(int(n * 0.95), n - 1)], 3
        )
        result["p99_latency_s"] = round(
            sorted_lat[min(int(n * 0.99), n - 1)], 3
        )

    return result


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


def get_int(prompt, min_val=1):
    while True:
        try:
            val = int(input(prompt).strip())
            if val < min_val:
                print(f"  Must be >= {min_val}. Try again.")
                continue
            return val
        except ValueError:
            print("  Enter a valid integer. Try again.")


def get_url(prompt):
    while True:
        val = input(prompt).strip()
        if val.startswith("http://") or val.startswith("https://"):
            return val
        print("  URL must start with http:// or https://. Try again.")


def merge_stats(totals, stage_result):
    for key in ("total_requests", "success", "server_errors",
                "timeouts", "connection_errors"):
        totals[key] = totals.get(key, 0) + stage_result[key]


async def main():
    banner()

    target = get_url(
        "Target URL (https://example.com): "
    )

    start_users = get_int("Initial concurrent users: ")

    ramp_step = get_int("Ramp-up increment: ")

    max_users = get_int(
        f"Maximum concurrent users (>= {start_users}): ",
        min_val=start_users
    )

    stage_duration = get_int("Duration per stage (seconds): ")

    timeout_value = get_int("HTTP timeout (seconds): ")

    cooldown = get_int("Cooldown between stages (seconds): ", min_val=0)

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
    print(f"Target               : {target}")
    print(f"Initial Users        : {start_users}")
    print(f"Ramp Increment       : {ramp_step}")
    print(f"Maximum Users        : {max_users}")
    print(f"Stage Duration       : {stage_duration}s")
    print(f"Timeout              : {timeout_value}s")
    print(f"Cooldown             : {cooldown}s")

    confirm = input(
        "\nProceed with validation? (yes/no): "
    ).lower()

    if confirm != "yes":
        print("\nAborted.")
        return

    report_file = (
        f"scrubbing_report_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    report = {
        "config": config,
        "started_at": datetime.now().isoformat(),
        "stages": [],
        "final_totals": {},
    }

    cumulative = {}
    current_users = start_users

    try:
        while current_users <= max_users:
            print("\n===================================")
            print(
                f" RUNNING STAGE: "
                f"{current_users} CONCURRENT USERS"
            )
            print("===================================\n")

            stage_start = time.time()

            stage_stats, stage_latencies = await run_stage(
                target,
                current_users,
                stage_duration,
                aiohttp.ClientTimeout(total=timeout_value)
            )

            elapsed = time.time() - stage_start
            result = compute_stats(stage_stats, stage_latencies, elapsed)
            result["concurrent_users"] = current_users
            result["duration_s"] = round(elapsed, 2)

            print(f"\nStage completed in {elapsed:.2f}s")
            print_stats("STAGE RESULTS", result)

            report["stages"].append(result)
            merge_stats(cumulative, result)

            # Save after each stage so partial results are never lost
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)

            if current_users + ramp_step <= max_users:
                print(
                    f"\nCooling down for "
                    f"{cooldown} seconds..."
                )
                await asyncio.sleep(cooldown)

            current_users += ramp_step

    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user — saving partial results...")

    print("\n===================================")
    print(" FINAL RESULTS")
    print("===================================")
    print_stats("CUMULATIVE TOTALS", cumulative)

    report["final_totals"] = cumulative
    report["completed_at"] = datetime.now().isoformat()

    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nReport saved → {report_file}")
    print("\nValidation completed.")


if __name__ == "__main__":
    asyncio.run(main())
