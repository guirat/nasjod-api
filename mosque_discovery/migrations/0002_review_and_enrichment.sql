ALTER TABLE staged_mosque
  ADD COLUMN image_url TEXT NULL,
  ADD COLUMN details JSONB NULL,
  ADD COLUMN enriched_at TIMESTAMPTZ NULL,
  ADD COLUMN enrich_error TEXT NULL,
  ADD COLUMN reviewed_by_id BIGINT NULL,
  ADD COLUMN reviewed_by_username TEXT NULL,
  ADD COLUMN reviewed_at TIMESTAMPTZ NULL,
  ADD COLUMN review_note TEXT NULL;

CREATE INDEX IF NOT EXISTS staged_mosque_source_enriched_at_idx ON staged_mosque (source, enriched_at);
