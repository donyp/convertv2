create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  status text not null default 'queued',
  progress int not null default 0,
  message text,
  filename text,
  bank text,
  validation_status text,
  transaction_count int,
  result_json jsonb,
  xlsx_bytes text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

-- Optional storage buckets (create in Supabase dashboard or via SQL):
-- insert into storage.buckets (id, name, public) values ('mutation-files', 'mutation-files', false)
-- on conflict (id) do nothing;
