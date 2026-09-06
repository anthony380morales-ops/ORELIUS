# Connect ORELIUS ⇄ NXG Life Group funnel (leads + traffic)

ORELIUS reads the NXG "Life Funnel" site (hosted on Netlify) every morning at
**8 AM PST** and briefs the Master on:

- **Leads** — every new lead captured since the last briefing, pulled from the
  **same Supabase project the private admin dashboard reads** (`public.leads`).
  If there are no new leads — or none at all — it says so plainly and still shows
  the standing pipeline snapshot.
- **Traffic** — **how many people and what devices** visited the site, from a
  lightweight `page_views` table in that same Supabase project.

```
  8 AM PST cron ──POST /api/automation/nxg-brief──▶ ORELIUS (Render)
                                                      │
                          ┌───────────────────────────┴───────────────────────────┐
                          ▼                                                         ▼
             Supabase `leads`  (leads the dashboard reads)        Supabase `page_views`  (visitors/devices)
```

Nothing about this touches the finance engine or the chat personality — it's a
separate ORELIUS automation with its own module (`app/core/nxg_intel.py`), its own
system prompt, and its own durable state. **Verified data only** — every figure is
a real Supabase/Netlify row; ORELIUS never invents a lead or a visitor count.

---

## Part A — ORELIUS side (already built & deployed)

Endpoints (secured with the same `X-Shared-Secret` as the finance brief):

| method | path | does |
|---|---|---|
| POST | `/api/automation/nxg-brief` | run the briefing now (leads + traffic) |
| GET  | `/api/automation/nxg-brief/latest` | read the most recent stored briefing |

### Environment variables to set in Render → Environment
```
NXG_SUPABASE_URL=https://bhuclkecnnbsovbdplwe.supabase.co   # already the default
NXG_SUPABASE_SERVICE_KEY=<Supabase service_role key>        # Supabase → Settings → API → service_role (secret)
```
Optional Netlify Analytics fallback for traffic (only if you use the paid add-on;
the free tracker in Part B is preferred and gives device data):
```
NETLIFY_API_TOKEN=<Netlify personal access token>
NETLIFY_SITE_ID=<the funnel site's API ID>
```

The `service_role` key bypasses RLS, which is exactly what a trusted backend
automation needs to read every lead. Keep it secret — it's set in Render's
environment, never committed.

### Schedule it (add a second job to the same cron service that runs the finance brief)
`POST https://orelius.onrender.com/api/automation/nxg-brief` daily at **8:00 AM
America/Los_Angeles**, header `X-Shared-Secret: <LUCIUS_SHARED_SECRET>`.

---

## Part B — LifeFunnel site: turn on people + device tracking (free)

The funnel currently only fires client-side Meta Pixel / GTM events — there's no
server-readable record of who visited. These three additions log visits into the
**same Supabase project** (privacy-preserving: no raw IP or user-agent is stored,
only a per-day per-person hash), so ORELIUS can report real people + device counts
with **no paid analytics add-on**. Copy them into the `LIFE FUNNEL/` directory of
your `LifeFunnel` repo:

1. **`supabase/migrations/0002_create_page_views.sql`** → run it once in the
   Supabase project (SQL Editor → paste → Run), or `supabase db push`.

2. **`netlify/functions/track-view.mjs`** → drop in as-is. It reuses the
   `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` you already set for the leads
   function — nothing new to configure. (Optional: `VISIT_HASH_SALT`.)

3. **`src/lib/visitTracker.ts`** → drop in, then wire the one existing hook point.
   In `src/App.tsx`, the `AnalyticsRouteLogger` already fires on every route
   change. Add two lines:

   ```diff
     import { trackPageView } from "@/lib/analytics";
   + import { recordVisit } from "@/lib/visitTracker";

     function AnalyticsRouteLogger() {
       const location = useLocation();
       useEffect(() => {
         trackPageView(location.pathname + location.search);
   +     recordVisit(location.pathname);
       }, [location.pathname, location.search]);
       return null;
     }
   ```

   Commit and let Netlify redeploy. From then on every visit is logged, and
   ORELIUS's morning briefing reports **people** (distinct daily visitors) and
   **devices** (mobile / tablet / desktop).

### Until Part B is deployed
The briefing still runs and reports leads fully; the Traffic section simply says
"traffic tracking not connected yet" instead of inventing numbers.
