from crawler.db import connect
from crawler.pipeline.types import OperatorInfo, ClassifyResult
from crawler.pipeline import orchestrator
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED, ALL_COMPLETED
from psycopg.rows import dict_row
import traceback
import random

MAX_CONCURRENT_JOBS = 25
JOB_LIMIT = 1
START_ROW = 0
MAX_JOB_ID = 234371 # not a perfect random sample, but sufficient for tests

def _insert_result(attraction_id, res: ClassifyResult):
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO results (
                attraction_id,
                final_url,
                operator_type,
                business_type,
                experience_type,
                is_commercial,
                booking_method,
                operating_scope,
                message,
                input_tokens,
                cached_input_tokens,
                output_tokens,
                searched
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (attraction_id) DO NOTHING
            """,
            (
                attraction_id,
                res.final_url,
                res.operator_type,
                res.business_type,
                res.experience_type,
                res.is_commercial_operator,
                res.booking_method,
                res.operating_scope,
                res.message,
                res.input_tokens,
                res.cached_input_tokens,
                res.output_tokens,
                res.searched,
            ),
        )

        for profile in res.profiles or []:
            cur.execute(
                """
                INSERT INTO profiles (
                    attraction_id,
                    profile_type,
                    role,
                    profile_name,
                    email,
                    phone,
                    whatsapp
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    attraction_id,
                    profile.profile_type,
                    profile.role,
                    profile.individual_name,
                    profile.email,
                    profile.phone,
                    profile.whatsapp,
                ),
            )

        cur.execute(
            """
            UPDATE jobs
            SET status = 'finished'
            WHERE attraction_id = %s
            """,
            (attraction_id,),
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
    _insert_result(row["attraction_id"], result)

    print(f"Finished {row['operator']}")

with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS) as ex:
    inflight = set()

    for _ in range(JOB_LIMIT):
        with connect(row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute("""
                WITH job AS (
                    SELECT id
                    FROM jobs
                    WHERE status = 'queued'
                      AND id >= %s
                    ORDER BY id
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE jobs
                SET status = 'running'
                FROM job
                WHERE jobs.id = job.id
                RETURNING jobs.*;
            """, (START_ROW,)) # random.randint(0, MAX_JOB_ID) for random sample
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