-- The small part of Supabase the migrations rely on. Local development only.
create role anon nologin;
create role authenticated nologin;
create schema auth;
grant usage on schema auth to anon, authenticated;
create table auth.users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  encrypted_password text not null,
  created_at timestamptz not null default now()
);
create function auth.uid() returns uuid language sql stable as $$
  select (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')::uuid
$$;
grant execute on function auth.uid() to anon, authenticated;
