import os
import csv
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ["DATABASE_URL"]

query = """
    SELECT *
    FROM jobs
    WHERE status IN ('finished', 'running')
    ORDER BY attraction_id
"""


def to_iso(ts) -> str:
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def trace_to_string(trace: dict | None) -> str:
    if not trace:
        return ""

    start_time = trace.get("start_time")
    steps = trace.get("steps", [])

    if start_time is None:
        return ""

    lines = []

    for e in steps:
        dt = e["t"] - start_time
        step = e["step"]
        parts = []
        for k, v in e.items():
            if k in {"t", "step"}:
                continue
            if k == "attempts":
                for attempt in v:
                    n = attempt.get("attempt")
                    info = ", ".join(
                        f"{ak}={av}" for ak, av in attempt.items() if ak != "attempt"
                    )
                    parts.append(f"attempt-{n}=({info})")
            else:
                parts.append(f"{k}={v}")
        meta = " ".join(parts)
        line = f"{f'[{dt:.2f}s]':>9} {step:<16} {meta}".rstrip()
        lines.append(line)

    return "\n".join(lines)


timestamp = f"{datetime.now():%Y%m%d_%H%M%S}"
export_path = Path("outputs") / f"{timestamp}_Export.csv"
profiles_path = Path("outputs") / f"{timestamp}_Profiles.csv"

with open(
    export_path,
    "w",
    newline="",
    encoding="utf-8-sig",
) as export_file, open(
    profiles_path,
    "w",
    newline="",
    encoding="utf-8-sig",
) as profiles_file:
    export_writer = csv.writer(export_file)
    profiles_writer = csv.writer(profiles_file)

    with psycopg.connect(DATABASE_URL) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query)
        rows = cur.fetchall()

    export_writer.writerow(
        [
            "Attraction ID",
            "Destination ID",
            "Trip Operator URL",
            "Operator Name",
            "Country",
            "State",
            "City",
            "Email",
            "Phone",
            "Operator Website",
            "Bookable",
            "Arrival Category",
            "Arrival Subcategory",
            "Average Rating",
            "Review Count",
            "Number of Products",
            "Operator Type",
            "Business Type",
            "Booking Method",
            "Commercial Operator",
            "Operating Scope",
            "Description",
            "Status",
            "Input Tokens",
            "Cached Input Tokens",
            "Output Tokens",
            "Message",
            "Searched",
            "Used Stealth",
            "Start Time",
            "Trace",
        ]
    )

    profiles_writer.writerow(
        [
            "Attraction ID",
            "Operator Name",
            "Final URL",
            "Profile Type",
            "Role",
            "Profile Name",
            "Email",
            "Phone",
            "WhatsApp",
        ]
    )

    for row in rows:
        result = row.get("result") or {}
        trace = row.get("trace") or {}
        profiles = result.get("profiles") or []

        export_writer.writerow(
            [
                row["attraction_id"],
                row["destination_id"],
                row["trip_operator_url"],
                row["operator"],
                row["country"],
                row["state"],
                row["city"],
                row["email"],
                row["phone"],
                row["operator_website"],
                row["bookable"],
                row["arival_category"],
                row["arival_sub_category"],
                row["avg_rating"],
                row["review_count"],
                row["number_of_products"],
                result.get("operator_type"),
                result.get("business_type"),
                result.get("booking_method"),
                result.get("is_commercial_operator"),
                result.get("operating_scope"),
                result.get("description"),
                row["status"],
                result.get("input_tokens"),
                result.get("cached_input_tokens"),
                result.get("output_tokens"),
                result.get("message"),
                result.get("searched"),
                result.get("used_stealth"),
                to_iso(trace.get("start_time")),
                trace_to_string(trace),
            ]
        )

        for profile in profiles:
            profiles_writer.writerow(
                [
                    row["attraction_id"],
                    row["operator"],
                    result.get("final_url"),
                    profile.get("profile_type"),
                    profile.get("role"),
                    profile.get("individual_name"),
                    profile.get("email"),
                    profile.get("phone"),
                    profile.get("whatsapp"),
                ]
            )

print("DB exported")
