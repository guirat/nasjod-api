DROP INDEX IF EXISTS staged_mosque_source_enriched_at_idx;

ALTER TABLE staged_mosque
  DROP COLUMN IF EXISTS image_url,
  DROP COLUMN IF EXISTS details,
  DROP COLUMN IF EXISTS enriched_at,
  DROP COLUMN IF EXISTS enrich_error,
  DROP COLUMN IF EXISTS reviewed_by_id,
  DROP COLUMN IF EXISTS reviewed_by_username,
  DROP COLUMN IF EXISTS reviewed_at,
  DROP COLUMN IF EXISTS review_note;
