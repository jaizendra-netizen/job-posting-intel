-- Job Posting Intel — Supabase schema
-- Paste into the Supabase SQL editor and run.

create extension if not exists pgcrypto;

-- 1) Target accounts ---------------------------------------------------------
create table if not exists accounts (
  id            uuid primary key default gen_random_uuid(),
  company_name  text not null,
  linkedin_url  text not null unique,
  status        text not null default 'pending',   -- pending | pulled | decoded | briefed | error
  posting_count int  default 0,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- 2) Every posting, RAW-FIRST ------------------------------------------------
-- The complete Blitz payload lives in `raw`. Claude's per-posting extraction lands in `decoded`.
create table if not exists job_postings (
  id           uuid primary key default gen_random_uuid(),
  account_id   uuid not null references accounts(id) on delete cascade,
  posting_key  text not null,              -- stable dedup key (id from Blitz, else hash)
  job_title    text,
  date_posted  date,
  posting_url  text,
  raw          jsonb not null,             -- the COMPLETE Blitz job object — never trim this
  decoded      jsonb,                      -- Claude decode: tools, seniority, comp, reports_to, responsibilities, signals
  decoded_at   timestamptz,
  created_at   timestamptz not null default now(),
  unique (account_id, posting_key)
);
create index if not exists job_postings_account_idx on job_postings(account_id);
create index if not exists job_postings_date_idx    on job_postings(date_posted);
create index if not exists job_postings_raw_gin     on job_postings using gin (raw);

-- 3) One intel brief per account --------------------------------------------
create table if not exists account_briefs (
  id                 uuid primary key default gen_random_uuid(),
  account_id         uuid not null references accounts(id) on delete cascade unique,
  company_name       text,
  stack              jsonb,     -- tools seen in requirements, with posting citations
  direction          text,      -- where the company is heading, per the postings
  budget_signals     text,      -- comp ranges × role counts read
  hierarchy          text,      -- reports-to structure observed
  strongest_movement text,      -- the single best thing to open outreach with
  icp_score          int check (icp_score between 0 and 5),
  score_reasoning    text,      -- ALWAYS store the model's reasoning — auditability
  outreach_draft     text,
  model              text,      -- which Claude model produced this
  created_at         timestamptz not null default now()
);

-- Lock the tables down: service-role key only (scripts), no anon access.
alter table accounts       enable row level security;
alter table job_postings   enable row level security;
alter table account_briefs enable row level security;
