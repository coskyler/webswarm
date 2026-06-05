CREATE TABLE jobs_stage (
    attraction_id        BIGINT,
    destination_id       BIGINT,
    trip_operator_url    TEXT,
    operator             TEXT,
    country              TEXT,
    state                TEXT,
    city                 TEXT,
    email                TEXT,
    phone                TEXT,
    operator_website     TEXT,
    bookable             TEXT,
    arival_category      TEXT,
    arival_sub_category  TEXT,
    avg_rating           NUMERIC(4,2),
    review_count         INTEGER,
    number_of_products   INTEGER
);

CREATE TABLE jobs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- from the dataset
    attraction_id        BIGINT UNIQUE NOT NULL,
    destination_id       BIGINT,
    trip_operator_url    TEXT,
    operator             TEXT,
    country              TEXT,
    state                TEXT,
    city                 TEXT,
    email                TEXT,
    phone                TEXT,
    operator_website     TEXT,
    bookable             TEXT,
    arival_category      TEXT,
    arival_sub_category  TEXT,
    avg_rating           NUMERIC(4,2),
    review_count         INTEGER,
    number_of_products   INTEGER,

    -- queue state
    status TEXT NOT NULL DEFAULT 'idle', -- idle | queued | running | finished | failed

    -- outputs
    result               JSONB,
    trace                JSONB
);

CREATE INDEX jobs_queued_idx ON jobs(attraction_id);
CREATE INDEX url_idx ON jobs(operator_website);