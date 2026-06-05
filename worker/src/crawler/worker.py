from crawler.db import connect
from crawler.pipeline.types import OperatorInfo, ClassifyResult
from crawler.pipeline import orchestrator
from crawler.pipeline.trace import Trace
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED, ALL_COMPLETED
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from urllib.request import Request, urlopen
import threading
import traceback
import random
import json
import os

MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS"))
START_ROW = int(os.getenv("START_ROW"))
END_ROW = int(os.getenv("END_ROW"))
MAX_JOB_ID = 234371 # not a perfect random sample, but sufficient for tests
IMDS_SPOT_INSTANCE_ACTION_URL = "http://169.254.169.254/latest/meta-data/spot/instance-action"
IMDS_TOKEN_URL = "http://169.254.169.254/latest/api/token"
IMDS_POLL_INTERVAL_SECONDS = 5
IMDS_TIMEOUT_SECONDS = 1

_spot_instance_shutting_down = threading.Event()


def _poll_imds_for_spot_interruption():
    while not _spot_instance_shutting_down.is_set():
        try:
            token_request = Request(
                IMDS_TOKEN_URL,
                method="PUT",
                headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            )
            with urlopen(token_request, timeout=IMDS_TIMEOUT_SECONDS) as response:
                token = response.read().decode()

            action_request = Request(
                IMDS_SPOT_INSTANCE_ACTION_URL,
                headers={"X-aws-ec2-metadata-token": token},
            )
            with urlopen(action_request, timeout=IMDS_TIMEOUT_SECONDS):
                _spot_instance_shutting_down.set()
        except OSError:
            pass

        _spot_instance_shutting_down.wait(IMDS_POLL_INTERVAL_SECONDS)


def _insert_result(attraction_id, res: ClassifyResult, trace: Trace):
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs
            SET status = 'finished',
                result = %s,
                trace = %s
            WHERE attraction_id = %s
            """,
            (Jsonb(res.model_dump()), Jsonb(trace.model_dump()), attraction_id),
        )

        conn.commit()


def job(row):
    print(f"Starting {row['operator']}")
    operator = OperatorInfo(
        name=row["operator"] or "",
        country=row["country"] or "",
        city=row["city"] or "",
        url=row["operator_website"] or ""
    )

    result, trace = orchestrator.run(operator)
    print(trace.to_string())
    print(json.dumps(result.model_dump(), indent=2))
    _insert_result(row["attraction_id"], result, trace)

    print(f"Finished {row['operator']}")

if os.getenv("ENVIRONMENT") == "production":
    threading.Thread(target=_poll_imds_for_spot_interruption, daemon=True).start()

with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS) as ex:
    inflight = set()

    while True:
        if _spot_instance_shutting_down.is_set():
            break

        with connect() as conn, conn.cursor() as cur:
            cur.execute("""
                WITH job AS (
                    SELECT id
                    FROM jobs
                    WHERE status = 'queued'
                      AND id >= %s
                      AND id <= %s
                    ORDER BY id
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE jobs
                SET status = 'running'
                FROM job
                WHERE jobs.id = job.id
                RETURNING jobs.*;
            """, (START_ROW, END_ROW)) # random.randint(0, MAX_JOB_ID) for random sample
            row = cur.fetchone()
            conn.commit()

        if row is None:
            break
        
        f = ex.submit(job, row)

        def log_exception(fut):
            exc = fut.exception()
            if exc:
                traceback.print_exception(type(exc), exc, exc.__traceback__)

        f.add_done_callback(log_exception)
        inflight.add(f)

        if len(inflight) >= MAX_CONCURRENT_JOBS:
            done, inflight = wait(inflight, return_when=FIRST_COMPLETED)

if inflight:
    wait(inflight, return_when=ALL_COMPLETED)

print("Worker done")