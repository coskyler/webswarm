# src/crawler/bootstrap.py
import os
import time
import socket
import json
import boto3
from urllib.parse import urlparse

def get_secrets():
    region = os.environ.get("AWS_REGION")
    sm = boto3.client("secretsmanager", region_name=region)

    def get(name):
        return sm.get_secret_value(SecretId=name)["SecretString"]

    creds = json.loads(get(os.environ["DB_CREDENTIALS_SECRET_NAME"]))

    os.environ["POSTGRES_USER"] = creds["username"]
    os.environ["POSTGRES_PASSWORD"] = creds["password"]
    os.environ["POSTGRES_DB"] = creds["dbname"]

    os.environ["OPENAI_API_KEY"] = get(os.environ["OPENAI_SECRET_NAME"])
    os.environ["BRIGHTDATA_SERP_API_KEY"] = get(os.environ["BRIGHTDATA_SERP_SECRET_NAME"])
    os.environ["BRIGHTDATA_FETCH_API_KEY"] = get(os.environ["BRIGHTDATA_FETCH_SECRET_NAME"])


def set_database_url():
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    host = os.environ["PGBOUNCER_HOST"]
    db = os.environ["POSTGRES_DB"]

    os.environ["DATABASE_URL"] = (
        f"postgresql://{user}:{password}@{host}:6432/{db}"
    )

def wait_for_postgres() -> None:
    url = os.environ["DATABASE_URL"]
    timeout = 15

    u = urlparse(url)
    host = u.hostname
    port = u.port

    deadline = time.time() + timeout

    while True:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"Postgres is reachable at {host}:{port}", flush=True)
                return
        except OSError:
            if time.time() >= deadline:
                raise SystemExit(f"Timed out waiting for Postgres at {host}:{port}")
            time.sleep(1)


def main() -> None:
    environment = os.environ["ENVIRONMENT"]

    if environment == "production": get_secrets()
    set_database_url()
    wait_for_postgres()

    os.execvp(
        "python",
        ["python", "-u", "-m", "crawler.worker"],
    )


if __name__ == "__main__":
    main()