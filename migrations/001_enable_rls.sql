-- Enable Row Level Security on all public tables.
--
-- The app connects via DATABASE_URL as the postgres superuser, which
-- bypasses RLS — no app changes needed. This blocks direct REST API
-- access (anon/authenticated keys) to all sensitive tables.
--
-- Run this once in the Supabase SQL editor.

ALTER TABLE public.entities     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.regulations  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_log    ENABLE ROW LEVEL SECURITY;

-- Regulations contain non-sensitive public AML rules; allow read via REST API.
-- Remove this if you want zero REST API exposure.
CREATE POLICY "authenticated_read_regulations"
  ON public.regulations
  FOR SELECT
  TO authenticated
  USING (true);
