-- social-scraper 收件佇列（冪等；收件服務啟動時執行）
CREATE TABLE IF NOT EXISTS scraper_jobs (
    id            bigserial PRIMARY KEY,
    url           text        NOT NULL,
    platform      text        NOT NULL CHECK (platform IN ('instagram', 'threads', 'github', 'article')),
    line_user_id  text,
    status        text        NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'working', 'done', 'error')),
    attempts      integer     NOT NULL DEFAULT 0,
    result_json   jsonb,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS scraper_jobs_status_created_idx ON scraper_jobs (status, created_at);
-- Supabase：public schema 會被 PostgREST 曝露，開 RLS 且不給 policy＝只有 DB 直連角色能讀寫
ALTER TABLE scraper_jobs ENABLE ROW LEVEL SECURITY;
