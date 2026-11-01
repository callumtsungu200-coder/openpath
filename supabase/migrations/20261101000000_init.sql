-- OpenPath schema. The worker connects with a privileged Postgres role and
-- bypasses RLS. The web app only ever uses anon/authenticated through RLS and
-- the RPC functions below.

create extension if not exists pg_trgm;

create type opportunity_category as enum (
  'apprenticeship', 'internship', 'work_experience', 'insight_programme',
  'graduate_scheme', 'placement', 'entry_level_job', 'job',
  'volunteering', 'scholarship', 'competition', 'course', 'other'
);
create type working_arrangement as enum ('remote', 'hybrid', 'in_person');
create type opportunity_status as enum ('active', 'expired', 'removed', 'duplicate', 'rejected');
create type verification_status as enum ('verified', 'pending', 'failed');
create type scan_status as enum ('running', 'success', 'partial', 'failed');
create type source_adapter as enum ('greenhouse', 'lever', 'ashby', 'jsonld_crawl', 'rendered');

create table sources (
  id bigint generated always as identity primary key,
  slug text not null unique,
  name text not null,
  adapter source_adapter not null,
  url text not null,
  config jsonb not null default '{}',
  company_name text,
  company_url text,
  logo_url text,
  company_description text,
  industry text,
  enabled boolean not null default true,
  scan_interval_minutes int not null default 360 check (scan_interval_minutes >= 15),
  next_scan_at timestamptz not null default now(),
  last_scan_at timestamptz,
  last_status scan_status,
  last_error text,
  consecutive_failures int not null default 0,
  created_at timestamptz not null default now()
);

create table scan_runs (
  id bigint generated always as identity primary key,
  source_id bigint not null references sources(id) on delete cascade,
  status scan_status not null default 'running',
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  pages_fetched int not null default 0,
  items_found int not null default 0,
  items_outside_uk int not null default 0,
  items_created int not null default 0,
  items_updated int not null default 0,
  items_unchanged int not null default 0,
  items_removed int not null default 0,
  items_pending int not null default 0,
  duplicates_found int not null default 0,
  ai_calls int not null default 0,
  error text
);
create index scan_runs_started_idx on scan_runs (started_at desc);
create index scan_runs_source_idx on scan_runs (source_id, started_at desc);

create table opportunities (
  id uuid primary key default gen_random_uuid(),
  source_id bigint not null references sources(id) on delete cascade,
  source_url text not null unique,
  apply_url text,
  external_id text,
  fingerprint text not null,
  content_hash text not null,
  title text not null,
  company_name text not null,
  company_logo_url text,
  category opportunity_category not null default 'other',
  industry text,
  location text,
  region text,
  arrangement working_arrangement,
  employment_type text,
  salary_min numeric,
  salary_max numeric,
  salary_period text check (salary_period in ('year', 'month', 'week', 'day', 'hour')),
  salary_text text,
  is_paid boolean,
  min_age int,
  max_age int,
  age_text text,
  deadline date,
  duration text,
  description text,
  responsibilities text[] not null default '{}',
  eligibility text[] not null default '{}',
  requirements text[] not null default '{}',
  programme_info text[] not null default '{}',
  extraction_method text not null default 'structured' check (extraction_method in ('structured', 'rules', 'ai', 'admin')),
  confidence numeric not null default 0,
  field_provenance jsonb not null default '{}',
  status opportunity_status not null default 'active',
  verification verification_status not null default 'pending',
  duplicate_of uuid references opportunities(id) on delete set null,
  missing_scans int not null default 0,
  posted_at timestamptz,
  discovered_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  last_verified_at timestamptz,
  search tsvector generated always as (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(company_name, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(industry, '') || ' ' || coalesce(location, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(description, '')), 'C')
  ) stored
);
create index opportunities_search_idx on opportunities using gin (search);
create index opportunities_title_trgm on opportunities using gin (title gin_trgm_ops);
create index opportunities_company_trgm on opportunities using gin (company_name gin_trgm_ops);
create index opportunities_public_idx on opportunities (status, verification, discovered_at desc);
create index opportunities_fingerprint_idx on opportunities (fingerprint);
create index opportunities_source_idx on opportunities (source_id);

create table duplicate_candidates (
  id bigint generated always as identity primary key,
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  candidate_id uuid not null references opportunities(id) on delete cascade,
  score numeric not null,
  status text not null default 'open' check (status in ('open', 'confirmed', 'dismissed')),
  created_at timestamptz not null default now(),
  unique (opportunity_id, candidate_id)
);

create table ai_runs (
  id bigint generated always as identity primary key,
  opportunity_url text,
  model text not null,
  purpose text not null,
  status text not null check (status in ('success', 'refused', 'error', 'skipped')),
  input_tokens int,
  output_tokens int,
  error text,
  created_at timestamptz not null default now()
);

create table opportunity_events (
  id bigint generated always as identity primary key,
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  kind text not null check (kind in ('discovered', 'updated', 'expired', 'removed', 'approved', 'rejected')),
  detail text,
  created_at timestamptz not null default now()
);
create index opportunity_events_recent_idx on opportunity_events (created_at desc);

create table worker_heartbeats (
  worker text primary key,
  last_seen_at timestamptz not null default now(),
  version text,
  redis_ok boolean,
  ai_enabled boolean not null default false
);

create table profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  is_admin boolean not null default false,
  created_at timestamptz not null default now()
);

create table saved_opportunities (
  user_id uuid not null references auth.users(id) on delete cascade,
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, opportunity_id)
);

create function handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (user_id) values (new.id) on conflict do nothing;
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function handle_new_user();

create function is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((select is_admin from profiles where user_id = auth.uid()), false)
$$;

-- Row level security: the public can read only live, verified opportunities.
alter table sources enable row level security;
alter table scan_runs enable row level security;
alter table opportunities enable row level security;
alter table duplicate_candidates enable row level security;
alter table ai_runs enable row level security;
alter table opportunity_events enable row level security;
alter table worker_heartbeats enable row level security;
alter table profiles enable row level security;
alter table saved_opportunities enable row level security;

create policy opportunities_public_read on opportunities for select
  using ((status = 'active' and verification = 'verified') or is_admin());
create policy events_public_read on opportunity_events for select using (
  exists (select 1 from opportunities o where o.id = opportunity_id)
);
create policy profiles_own on profiles for select using (user_id = auth.uid());
create policy saved_own on saved_opportunities for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy sources_admin on sources for select using (is_admin());
create policy scan_runs_admin on scan_runs for select using (is_admin());
create policy duplicates_admin on duplicate_candidates for select using (is_admin());
create policy ai_runs_admin on ai_runs for select using (is_admin());
create policy heartbeats_admin on worker_heartbeats for select using (is_admin());

-- Search and browse.
create function search_opportunities(
  q text default null,
  categories opportunity_category[] default null,
  industries text[] default null,
  regions text[] default null,
  arrangements working_arrangement[] default null,
  paid boolean default null,
  age int default null,
  deadline_within_days int default null,
  has_deadline boolean default null,
  sort text default 'relevance',
  page_size int default 24,
  page_offset int default 0
) returns jsonb
language sql stable set search_path = public as $$
  with query as (
    select nullif(trim(q), '') as raw,
           case when nullif(trim(q), '') is null then null
                else websearch_to_tsquery('english', q) end as ts
  ), matches as (
    select o.*, case when query.raw is null then 0
             else ts_rank(o.search, query.ts) + similarity(o.title, query.raw) end as rank
    from opportunities o, query
    where o.status = 'active' and o.verification = 'verified'
      and (query.raw is null or o.search @@ query.ts
           or o.title % query.raw or o.company_name % query.raw)
      and (categories is null or o.category = any(categories))
      and (industries is null or o.industry = any(industries))
      and (regions is null or o.region = any(regions))
      and (arrangements is null or o.arrangement = any(arrangements))
      and (paid is null or o.is_paid = paid)
      and (age is null or (
        (o.min_age is not null or o.max_age is not null)
        and (o.min_age is null or o.min_age <= age)
        and (o.max_age is null or o.max_age >= age)))
      and (deadline_within_days is null or (
        o.deadline is not null and o.deadline <= current_date + deadline_within_days))
      and (has_deadline is null or (o.deadline is not null) = has_deadline)
  ), ordered as (
    select * from matches
    order by
      case when sort = 'deadline' then deadline end asc nulls last,
      case when sort = 'salary' then coalesce(salary_max, salary_min) end desc nulls last,
      case when sort = 'relevance' then rank end desc,
      discovered_at desc, id
    limit least(page_size, 60) offset greatest(page_offset, 0)
  )
  select jsonb_build_object(
    'total', (select count(*) from matches),
    'items', coalesce((select jsonb_agg(to_jsonb(ordered) - 'search' - 'rank' - 'fingerprint' - 'content_hash') from ordered), '[]'::jsonb)
  )
$$;

create function search_suggestions(q text) returns jsonb
language sql stable set search_path = public as $$
  with live as (
    select title, company_name from opportunities
    where status = 'active' and verification = 'verified'
  ), hits as (
    (select distinct title as label, 'title' as kind, similarity(title, q) as score
       from live where title ilike '%' || q || '%' order by score desc limit 5)
    union all
    (select distinct company_name, 'company', similarity(company_name, q)
       from live where company_name ilike '%' || q || '%' order by 3 desc limit 3)
  )
  select coalesce(jsonb_agg(jsonb_build_object('label', label, 'kind', kind) order by score desc), '[]'::jsonb)
  from hits where length(trim(q)) >= 2
$$;

create function get_opportunity(opportunity uuid) returns jsonb
language sql stable set search_path = public as $$
  select to_jsonb(o) - 'search' - 'fingerprint' - 'content_hash'
  from opportunities o where o.id = opportunity
$$;

-- Source facts a public detail page needs, without exposing scan internals.
create function get_opportunity_source(opportunity uuid) returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object(
    'name', s.name, 'adapter', s.adapter,
    'company_url', s.company_url, 'company_description', s.company_description
  )
  from sources s join opportunities o on o.source_id = s.id
  where o.id = opportunity
    and ((o.status = 'active' and o.verification = 'verified') or is_admin())
$$;

create function home_feed() returns jsonb
language sql stable security definer set search_path = public as $$
  with live as (
    select * from opportunities where status = 'active' and verification = 'verified'
  ), card as (
    select to_jsonb(l) - 'search' - 'fingerprint' - 'content_hash' - 'description'
           - 'responsibilities' - 'eligibility' - 'requirements' - 'programme_info' as j,
           l.* from live l
  )
  select jsonb_build_object(
    -- At most two per employer, so one large scan cannot fill the section.
    'recent', coalesce((select jsonb_agg(j) from (
        select j from (
          select j, discovered_at, id, row_number() over (partition by company_name order by discovered_at desc, id) as n
          from card) ranked
        where n <= 2 order by discovered_at desc, id limit 6) r), '[]'::jsonb),
    -- Featured is earned, never paid: early-career roles with the most stated facts.
    'featured', coalesce((select jsonb_agg(j) from (
        select j from (
          select j, deadline, discovered_at, id, facts,
                 row_number() over (partition by company_name order by facts desc, deadline asc nulls last, id) as n
          from (select j, deadline, discovered_at, id, company_name,
                  (salary_min is not null or salary_text is not null)::int + (deadline is not null)::int
                  + (min_age is not null)::int + (arrangement is not null)::int as facts
                from card where category not in ('job', 'other')) scored) ranked
        where n = 1 order by facts desc, deadline asc nulls last, discovered_at desc, id
        limit 3) f), '[]'::jsonb),
    'categories', coalesce((select jsonb_agg(jsonb_build_object('category', category, 'count', n) order by n desc)
        from (select category, count(*) n from live group by category) c), '[]'::jsonb),
    'industries', coalesce((select jsonb_agg(jsonb_build_object('industry', industry, 'count', n) order by n desc)
        from (select industry, count(*) n from live where industry is not null
              group by industry order by n desc limit 8) i), '[]'::jsonb),
    'updates', coalesce((select jsonb_agg(u order by (u->>'created_at') desc) from (
        select jsonb_build_object('id', e.id, 'kind', e.kind, 'detail', e.detail, 'created_at', e.created_at,
                 'opportunity_id', o.id, 'title', o.title, 'company_name', o.company_name) u
        from opportunity_events e join live o on o.id = e.opportunity_id
        where e.kind in ('discovered', 'updated')
        order by e.created_at desc, e.id desc limit 6) x), '[]'::jsonb),
    'stats', jsonb_build_object(
      'active', (select count(*) from live),
      'companies', (select count(distinct company_name) from live),
      'discovered_7d', (select count(*) from live where discovered_at > now() - interval '7 days'),
      'sources_monitored', (select count(*) from sources where enabled),
      'last_scan_at', (select max(finished_at) from scan_runs where status in ('success', 'partial'))
    )
  )
$$;

create function search_facets() returns jsonb
language sql stable set search_path = public as $$
  with live as (select * from opportunities where status = 'active' and verification = 'verified')
  select jsonb_build_object(
    'industries', coalesce((select jsonb_agg(jsonb_build_object('value', industry, 'count', n) order by n desc)
       from (select industry, count(*) n from live where industry is not null group by industry) i), '[]'::jsonb),
    'regions', coalesce((select jsonb_agg(jsonb_build_object('value', region, 'count', n) order by n desc)
       from (select region, count(*) n from live where region is not null group by region) r), '[]'::jsonb),
    'categories', coalesce((select jsonb_agg(jsonb_build_object('value', category, 'count', n) order by n desc)
       from (select category, count(*) n from live group by category) c), '[]'::jsonb)
  )
$$;

-- Saved opportunities.
create function toggle_saved(opportunity uuid) returns boolean
language plpgsql set search_path = public as $$
begin
  if auth.uid() is null then raise exception 'Sign in to save opportunities' using errcode = '28000'; end if;
  delete from saved_opportunities where user_id = auth.uid() and opportunity_id = opportunity;
  if found then return false; end if;
  insert into saved_opportunities (user_id, opportunity_id) values (auth.uid(), opportunity);
  return true;
end $$;

create function my_saved() returns jsonb
language sql stable set search_path = public as $$
  select coalesce(jsonb_agg(to_jsonb(o) - 'search' - 'fingerprint' - 'content_hash' - 'description' order by s.created_at desc), '[]'::jsonb)
  from saved_opportunities s join opportunities o on o.id = s.opportunity_id
  where s.user_id = auth.uid()
$$;

create function my_saved_ids() returns jsonb
language sql stable set search_path = public as $$
  select coalesce(jsonb_agg(opportunity_id), '[]'::jsonb) from saved_opportunities where user_id = auth.uid()
$$;

create function my_profile() returns jsonb
language sql stable set search_path = public as $$
  select jsonb_build_object('is_admin', is_admin()) where auth.uid() is not null
$$;

-- Admin. Every function checks is_admin() itself because it runs as definer.
create function require_admin() returns void
language plpgsql stable set search_path = public as $$
begin
  if not is_admin() then raise exception 'Admin access required' using errcode = '42501'; end if;
end $$;

create function admin_overview() returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare result jsonb;
begin
  perform require_admin();
  select jsonb_build_object(
    'counts', jsonb_build_object(
      'discovered', (select count(*) from opportunities),
      'active', (select count(*) from opportunities where status = 'active' and verification = 'verified'),
      'expired', (select count(*) from opportunities where status = 'expired'),
      'removed', (select count(*) from opportunities where status = 'removed'),
      'pending', (select count(*) from opportunities where status = 'active' and verification = 'pending'),
      'duplicates_open', (select count(*) from duplicate_candidates where status = 'open'),
      'duplicates_merged', (select count(*) from opportunities where status = 'duplicate'),
      'failed_scans_24h', (select count(*) from scan_runs where status = 'failed' and started_at > now() - interval '24 hours'),
      'scans_24h', (select count(*) from scan_runs where started_at > now() - interval '24 hours'),
      'ai_calls_24h', (select count(*) from ai_runs where created_at > now() - interval '24 hours' and status <> 'skipped')
    ),
    'daily', coalesce((select jsonb_agg(d order by d->>'day') from (
       select jsonb_build_object('day', to_char(day, 'YYYY-MM-DD'),
         'success', count(r.id) filter (where r.status in ('success', 'partial')),
         'failed', count(r.id) filter (where r.status = 'failed'),
         'created', coalesce(sum(r.items_created), 0)) d
       from generate_series(current_date - 13, current_date, interval '1 day') day
       left join scan_runs r on r.started_at >= day and r.started_at < day + interval '1 day'
       group by day) x), '[]'::jsonb),
    'sources', coalesce((select jsonb_agg(s order by s->>'name') from (
       select jsonb_build_object('id', s.id, 'name', s.name, 'adapter', s.adapter, 'url', s.url, 'enabled', s.enabled,
         'last_scan_at', s.last_scan_at, 'last_status', s.last_status, 'last_error', s.last_error,
         'next_scan_at', s.next_scan_at, 'consecutive_failures', s.consecutive_failures,
         'active_count', (select count(*) from opportunities o where o.source_id = s.id and o.status = 'active')) s
       from sources s) x), '[]'::jsonb),
    'scans', coalesce((select jsonb_agg(to_jsonb(r) order by r.started_at desc) from (
       select sr.*, s.name as source_name from scan_runs sr join sources s on s.id = sr.source_id
       order by sr.started_at desc limit 25) r), '[]'::jsonb),
    'pending', coalesce((select jsonb_agg(p) from (
       select jsonb_build_object('id', id, 'title', title, 'company_name', company_name, 'category', category,
         'confidence', confidence, 'extraction_method', extraction_method, 'source_url', source_url,
         'discovered_at', discovered_at) p
       from opportunities where status = 'active' and verification = 'pending'
       order by discovered_at desc limit 25) x), '[]'::jsonb),
    'duplicates', coalesce((select jsonb_agg(d) from (
       select jsonb_build_object('id', c.id, 'score', c.score, 'a_id', a.id, 'a_title', a.title, 'a_url', a.source_url,
         'b_id', b.id, 'b_title', b.title, 'b_url', b.source_url, 'company_name', a.company_name) d
       from duplicate_candidates c join opportunities a on a.id = c.opportunity_id
       join opportunities b on b.id = c.candidate_id
       where c.status = 'open' order by c.score desc limit 25) x), '[]'::jsonb),
    'expired', coalesce((select jsonb_agg(e) from (
       select jsonb_build_object('id', id, 'title', title, 'company_name', company_name, 'status', status,
         'deadline', deadline, 'last_seen_at', last_seen_at) e
       from opportunities where status in ('expired', 'removed')
       order by last_seen_at desc limit 25) x), '[]'::jsonb),
    'ai', coalesce((select jsonb_agg(to_jsonb(a) order by a.created_at desc) from (
       select * from ai_runs order by created_at desc limit 25) a), '[]'::jsonb),
    'health', jsonb_build_object(
      'workers', coalesce((select jsonb_agg(to_jsonb(w) order by w.last_seen_at desc) from worker_heartbeats w), '[]'::jsonb),
      'database_ok', true,
      'checked_at', now()
    )
  ) into result;
  return result;
end $$;

create function admin_review_opportunity(opportunity uuid, approve boolean) returns void
language plpgsql security definer set search_path = public as $$
begin
  perform require_admin();
  update opportunities set
    verification = case when approve then 'verified'::verification_status else 'failed'::verification_status end,
    status = case when approve then status else 'rejected'::opportunity_status end,
    last_verified_at = case when approve then now() else last_verified_at end,
    updated_at = now()
  where id = opportunity;
  insert into opportunity_events (opportunity_id, kind, detail)
  values (opportunity, case when approve then 'approved' else 'rejected' end, 'Reviewed by an administrator');
end $$;

create function admin_resolve_duplicate(candidate bigint, is_duplicate boolean) returns void
language plpgsql security definer set search_path = public as $$
declare pair duplicate_candidates;
begin
  perform require_admin();
  update duplicate_candidates set status = case when is_duplicate then 'confirmed' else 'dismissed' end
    where id = candidate returning * into pair;
  if is_duplicate then
    update opportunities set status = 'duplicate', duplicate_of = pair.candidate_id, updated_at = now()
      where id = pair.opportunity_id;
  end if;
end $$;

create function admin_set_source_enabled(source bigint, enable boolean) returns void
language plpgsql security definer set search_path = public as $$
begin
  perform require_admin();
  update sources set enabled = enable, next_scan_at = case when enable then now() else next_scan_at end
    where id = source;
end $$;

create function admin_request_scan(source bigint) returns void
language plpgsql security definer set search_path = public as $$
begin
  perform require_admin();
  update sources set next_scan_at = now() where id = source;
end $$;

-- Least privilege: nothing is callable or readable unless granted here.
revoke all on all functions in schema public from public, anon, authenticated;
revoke all on all tables in schema public from anon, authenticated;
grant usage on schema public to anon, authenticated;
-- pg_trgm lives in public, so the blanket revoke above also caught these.
grant execute on function similarity(text, text), similarity_op(text, text), show_limit() to anon, authenticated;
grant select on opportunities, opportunity_events to anon, authenticated;
grant select on sources, scan_runs, duplicate_candidates, ai_runs, worker_heartbeats, profiles to authenticated;
grant select, insert, delete on saved_opportunities to authenticated;
grant execute on function is_admin() to anon, authenticated;
grant execute on function search_opportunities(text, opportunity_category[], text[], text[], working_arrangement[], boolean, int, int, boolean, text, int, int) to anon, authenticated;
grant execute on function search_suggestions(text) to anon, authenticated;
grant execute on function search_facets() to anon, authenticated;
grant execute on function get_opportunity(uuid) to anon, authenticated;
grant execute on function get_opportunity_source(uuid) to anon, authenticated;
grant execute on function home_feed() to anon, authenticated;
grant execute on function toggle_saved(uuid), my_saved(), my_saved_ids(), my_profile() to authenticated;
grant execute on function require_admin() to authenticated;
grant execute on function admin_overview(), admin_review_opportunity(uuid, boolean), admin_resolve_duplicate(bigint, boolean), admin_set_source_enabled(bigint, boolean), admin_request_scan(bigint) to authenticated;
