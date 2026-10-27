-- the clep engine (product clips recorded from a live page)
ALTER TABLE jobs DROP CONSTRAINT jobs_engine_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_engine_check CHECK (engine IN ('reels', 'motion', 'clep'));

-- a job may end in a result instead of a video (clep feature scans: the list of data-clep features)
ALTER TABLE jobs ADD COLUMN result jsonb;

-- new keys may call every engine unless told otherwise; existing keys keep the engines they were given
ALTER TABLE access_keys ALTER COLUMN engines SET DEFAULT '{reels,motion,clep}';
