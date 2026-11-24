CREATE TABLE IF NOT EXISTS staged_mosque (
    id                  BIGSERIAL PRIMARY KEY,
    source              TEXT NOT NULL,              -- 'mawaqit' | 'google_places'
    source_id           TEXT NOT NULL,
    name                TEXT NOT NULL DEFAULT '',
    name_ar             TEXT,
    lat                 DOUBLE PRECISION NOT NULL,
    lon                 DOUBLE PRECISION NOT NULL,
    geom                geography(Point, 4326),
    address             TEXT,
    city                TEXT,
    state               TEXT,
    zip_code            TEXT,
    country             TEXT,
    phone               TEXT,
    raw                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    status              TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN ('new','approved','rejected','imported','duplicate')),
    duplicate_of_id     BIGINT REFERENCES staged_mosque(id) ON DELETE SET NULL,
    matched_masjid_id   BIGINT,                     -- main DB Masjid id (set by import_staged_mosques)
    match_distance_m    DOUBLE PRECISION,
    match_name_score    DOUBLE PRECISION,
    first_seen          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_id)
);
CREATE INDEX IF NOT EXISTS staged_mosque_status_idx ON staged_mosque (status);
CREATE INDEX IF NOT EXISTS staged_mosque_geom_idx ON staged_mosque USING GIST (geom);
