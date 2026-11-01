# OpenPath

OpenPath automatically discovers UK opportunities (apprenticeships, internships, graduate schemes, jobs and more) from employers' own sites, keeps them up to date, and makes them searchable.

Nothing in the product is sample data. Every listing comes from a real scan, and an empty database shows empty states.

```
web/        React, TypeScript, Vite, Tailwind, shadcn/ui. Deploys to Vercel.
supabase/   Postgres schema, row level security and search functions.
worker/     Python discovery engine: Scrapy, Playwright, Celery, Redis, Claude API.
local/      Runs everything on one PC with real Postgres. No accounts or Docker needed.
```

## How discovery works

1. **Schedule.** Celery beat finds sources that are due every 5 minutes and queues them through Redis.
2. **Fetch.** Scrapy reads public job board APIs (Greenhouse, Lever, Ashby) and crawls career sites for schema.org `JobPosting` data. Playwright handles sites built with JavaScript. `robots.txt` is obeyed and requests are throttled.
3. **Extract.** Rules read the title, category, location, pay, age, deadline and sections. A fact only counts if the listing states it.
4. **AI, selectively.** Claude is called only when rules leave a listing below the confidence threshold, with a per-scan cap. Each value must quote the listing, and any quote not found in the source is thrown away. Without an API key, uncertain listings wait in the review queue.
5. **Deduplicate.** Exact matches across sources merge automatically. Near matches go to an administrator.
6. **Monitor.** Listings missing from two complete scans in a row are retired. Partial or failed scans are never treated as evidence of removal. Past deadlines expire overnight. Crawled links are rechecked hourly. Failing sources back off automatically.

## Run it locally

Needs Node 20+ and Python 3.11+. In one terminal:

```bash
cd local && npm install && npm start
```

In a second terminal (on Windows, activate with `.venv\Scripts\activate`, and set `DATABASE_URL` with `$env:DATABASE_URL="..."`):

```bash
cd worker
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
export DATABASE_URL="postgresql://postgres@127.0.0.1:54329/postgres?sslmode=disable"
openpath sources sync
openpath scan-all
```

In a third terminal:

```bash
cd web && cp .env.example .env.local
```

Set the two local values from that file, then:

```bash
npm install && npm run dev
```

To use the admin dashboard, create an account in the app, then:

```bash
cd local && npm run make-admin -- you@example.com
```

## Tests

```bash
cd worker && pytest
```

Set `OPENPATH_TEST_DATABASE_URL` to the local database URL to include the database tests. Without it they are skipped.

## Deploy

1. **Database.** Create a Supabase project and run `supabase db push`, or paste the file in `supabase/migrations` into the SQL editor.
2. **Web.** Import the repo into Vercel with `web` as the root directory. Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
3. **Worker.** On any Docker host (Railway, Fly, a VPS), copy `worker/.env.example` to `worker/.env`, fill it in, and run `docker compose up -d`. Then run `openpath sources sync` once. Vercel cannot run the worker because scans are long-running.
4. **First admin.** Sign up, then in the Supabase SQL editor run: `update profiles set is_admin = true where user_id = (select id from auth.users where email = 'you@example.com');`

## Adding sources

Add an entry to `worker/sources.yaml` and run `openpath sources sync`. Check the site's terms first. Prefer official APIs and feeds to crawling.

### Apprenticeships

These come from GOV.UK's official Find an apprenticeship service through its Display Advert API. Create a free account at https://developer.apprenticeships.education.gov.uk/third-party-accounts/register, put the key in `worker/.env` as `FIND_APPRENTICESHIP_API_KEY`, then run:

```bash
openpath sources sync
openpath scan find-an-apprenticeship
```

The source stays paused, and is not counted as monitored, until the key is set. Employer contact details in the API are deliberately not stored. Each listing links to its GOV.UK advert and to the application page the advert names. The service covers England.

### Work experience

Three scanners cover school and college students, including virtual programmes:

- **Springpod** (`springpod`): reads its public sitemaps and keeps programmes with a live cohort. Anything behind Springpod's free account stays there, and applicants are sent to its page.
- **Futures For All Work Experience Finder** (`futures_finder`): visits each public listing with Playwright. Applying needs a free account on their site.
- **Official pages** (`programme_pages`, in `sources.yaml`): organisations' own pages. Only the name, organisation and place are set by hand. Dates, ages, and whether applications are open are read from the page on every scan, and short excerpts are kept rather than whole pages.

A programme's page often survives between rounds, so `application_status` says `open`, `closed`, or null when the page does not say. A past date on such a page means a closed round, not an expired listing.

"Verified" here means the listing was found on that organisation's or platform's own site and rechecked by the scanner. It is not an endorsement or a safeguarding check. Sites whose `robots.txt` disallows us are deliberately not scanned, even when they run good programmes. When this was built that included The Forage, UCAS, Nuffield Research Placements, the Sutton Trust, In2scienceUK, Parliament, and several NHS trusts and law firms. Ask them for access before adding them. Springpod's terms refer to an Acceptable Use Policy that could not be found publicly, so check it with them before launch.

## Design system

The look is light frosted glass with black pills, combined with iOS conventions: a floating tab bar on phones, bottom sheets, segmented controls, press feedback, and San Francisco on Apple devices (Inter elsewhere). Tokens are in `web/src/index.css`, components in `web/src/components/ui`, and a living reference is at `/design-system`. All colours are tokens, so changing that one block restyles most of the product. The page background gradient also sits there, and cards turn black on hover through `group-hover` classes in `OpportunityCard.tsx`.

## Assumptions made

The original technical specification was not available, so these were decided from the brief. Review them:

- **Scope.** Experienced jobs are included, because the data sources are mostly jobs. Featured and early-career views exclude them.
- **"Verified"** means found in the employer's own listing with enough confidence, and rechecked on each scan. It does not mean a person checked it.
- **Paid.** Jobs with no pay figure are treated as paid, and the detail page says this is assumed. Internships with no statement stay unknown.
- **Age.** Only explicit statements count. Most employers state none, so the age filter excludes most listings and says so. Apprenticeships are the exception: they show 16+, labelled as the general rule for apprenticeships in England rather than something the advert stated.
- **Logos** are shown only when a source supplies one. Otherwise initials are shown, rather than fetching brand assets from elsewhere.
- **AI model** defaults to `claude-opus-5-5`, with server-side refusal fallbacks on. Set `OPENPATH_AI_MODEL` to change it. Haiku would be much cheaper for this job and is worth evaluating.

## Before a public launch

- Add a privacy policy and terms. Users may be under 18, so UK GDPR and the Children's Code apply to accounts.
- Have each source's terms reviewed, and set `OPENPATH_USER_AGENT` to name a real contact URL.
- Turn on email confirmation and rate limits in Supabase Auth.
