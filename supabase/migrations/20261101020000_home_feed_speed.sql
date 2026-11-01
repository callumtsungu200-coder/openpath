-- Ranks on light columns and builds card JSON only for the rows shown, so the cost stays flat as
-- listings grow. Featured now spans categories, so one large source cannot fill the section.
create or replace function opportunity_card(o opportunities) returns jsonb
language sql immutable as $$
  select to_jsonb(o) - 'search' - 'fingerprint' - 'content_hash' - 'description' - 'company_description'
         - 'responsibilities' - 'eligibility' - 'requirements' - 'programme_info'
$$;
revoke all on function opportunity_card(opportunities) from public, anon, authenticated;

create or replace function home_feed() returns jsonb
language sql stable security definer set search_path = public as $$
  with live as (
    select id, company_name, category, industry, discovered_at, deadline, arrangement,
           salary_min, salary_text, min_age
    from opportunities where status = 'active' and verification = 'verified'
  ), recent_ids as (
    select id, discovered_at from (
      select id, discovered_at,
             row_number() over (partition by company_name order by discovered_at desc, id) as n
      from live) ranked
    where n <= 2 order by discovered_at desc, id limit 6
  ), scored as (
    select id, company_name, category, deadline, discovered_at,
           (salary_min is not null or salary_text is not null)::int + (deadline is not null)::int
           + (min_age is not null)::int + (arrangement is not null)::int as facts
    from live where category not in ('job', 'other')
      and (deadline is null or deadline >= current_date + 7)
  ), featured_ids as (
    select id, facts, deadline, discovered_at from (
      select id, facts, deadline, discovered_at,
             row_number() over (partition by category order by facts desc, deadline asc nulls last, discovered_at desc, id) as n
      from (
        select *, row_number() over (partition by company_name order by facts desc, deadline asc nulls last, id) as per_company
        from scored) s
      where per_company = 1) ranked
    where n = 1 order by facts desc, deadline asc nulls last, discovered_at desc, id limit 3
  ), latest_events as (
    select e.id, e.kind, e.detail, e.created_at, e.opportunity_id
    from opportunity_events e
    where e.kind in ('discovered', 'updated')
      and exists (select 1 from live l where l.id = e.opportunity_id)
    order by e.created_at desc, e.id desc limit 6
  )
  select jsonb_build_object(
    'recent', coalesce((select jsonb_agg(opportunity_card(o) order by r.discovered_at desc, r.id)
        from recent_ids r join opportunities o using (id)), '[]'::jsonb),
    'featured', coalesce((select jsonb_agg(opportunity_card(o) order by f.facts desc, f.deadline asc nulls last, f.discovered_at desc, f.id)
        from featured_ids f join opportunities o using (id)), '[]'::jsonb),
    'categories', coalesce((select jsonb_agg(jsonb_build_object('category', category, 'count', n) order by n desc)
        from (select category, count(*) n from live group by category) c), '[]'::jsonb),
    'industries', coalesce((select jsonb_agg(jsonb_build_object('industry', industry, 'count', n) order by n desc)
        from (select industry, count(*) n from live where industry is not null
              group by industry order by n desc limit 8) i), '[]'::jsonb),
    'updates', coalesce((select jsonb_agg(jsonb_build_object('id', e.id, 'kind', e.kind, 'detail', e.detail, 'created_at', e.created_at,
                 'opportunity_id', o.id, 'title', o.title, 'company_name', o.company_name) order by e.created_at desc, e.id desc)
        from latest_events e join opportunities o on o.id = e.opportunity_id), '[]'::jsonb),
    'stats', jsonb_build_object(
      'active', (select count(*) from live),
      'companies', (select count(distinct company_name) from live),
      'discovered_7d', (select count(*) from live where discovered_at > now() - interval '7 days'),
      'sources_monitored', (select count(*) from sources where enabled),
      'last_scan_at', (select max(finished_at) from scan_runs where status in ('success', 'partial'))
    )
  )
$$;
