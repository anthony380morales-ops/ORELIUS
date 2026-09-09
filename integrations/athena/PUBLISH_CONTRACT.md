# ORELIUS → ATHENA publish contract (multi-account)

This is the exact shape ORELIUS sends when it dispatches a compiled post for a
specific account. Build ATHENA's account-aware handler to read these fields.

## Current ATHENA state (audited)

ATHENA today is **single-brand**: `env.BRAND_HANDLE = "@her.iron.will"` is hardwired
across design, publish, status, and monetization. There is **no account registry,
no `accountId`, no `brands/` directory** in the committed repo. So the account keys
below are **defined here** and both sides adopt them — there were no existing keys
to match.

Also: the committed `/jobs` handler reads only `body.action` and `body.days`, and
`action:"once"` runs ATHENA's own autopilot for `BRAND_HANDLE`. That is why ORELIUS
content was ignored and only `@her.iron.will` posted.

## The action

`action: "publish"` — a NEW `/jobs` action that publishes **ORELIUS-supplied**
content to the account named by `accountId` (as opposed to `once`, which generates
ATHENA's own content). Add `"publish"` to ATHENA's `ACTIONS` and branch on it in
`executeAction`.

ORELIUS sends this action by default (`ATHENA_CONTENT_ACTION=publish`). Until
ATHENA's `publish` handler is live, ATHENA returns 400 and the bridge now **skips**
the request (reports it once, no retry loop) instead of hanging.

## The account keys (canonical — mirror these in ATHENA's account profiles)

| accountId | brandId | platform | format | destination |
|---|---|---|---|---|
| `herironwill` | `HERIRONWILL` | instagram | reel/carousel/quote | existing @her.iron.will (unchanged) |
| `ibluezcluezflow` | `IBC` | instagram | `reel` | ibluezcluezflow IG |
| `nxg_life_group` | `NXG` | facebook | `facebook_post` | NXG Life Group Facebook page |

## The job body ORELIUS → bridge → `POST /jobs`

```jsonc
{
  "action":   "publish",
  "accountId": "nxg_life_group",     // WHICH account — route to its profile
  "brandId":   "NXG",
  "brand":     "NXG Life Group",
  "platform":  "facebook",           // instagram | facebook
  "target":    "facebook_page",      // instagram_reels | facebook_page
  "format":    "facebook_post",      // reel | facebook_post
  "publish":   true,
  "content": {                        // the EXACT post ORELIUS compiled — publish this
    "caption":   "…full caption…",
    "hashtags":  "#one #two #three",
    "post_idea": "the concept in 1-3 sentences",
    "facts":     ["verified fact 1", "verified fact 2", "verified fact 3"]
  },
  "brief": "…the same content as a human-readable text block…"
}
```

## What ATHENA's `publish` handler must do

1. **Resolve the account** from `accountId`. If unknown → STOP, do not fall back to
   `herironwill` (brand isolation). Report missing profile.
2. **Use `content` verbatim** as the post copy — do NOT generate a new topic. The
   `facts` are already verified by ORELIUS (economic briefing); do not invent more.
3. **Pick the medium** from `format`/`platform` (reel → IG reel; facebook_post → FB
   feed post) and send the account's **brand creative context** to HIGGBOT so the
   visual matches that account (not herironwill's look).
4. **Publish to that account** (IG Graph for IG, the FB page for NXG), run the same
   QA gate, and return the normal job result the bridge polls.

## Field name mismatches?

If ATHENA's handler ends up reading different key names (e.g. `platform` vs
`channel`, or `content.body` vs `caption`), tell ORELIUS and it will match them
exactly — the goal is zero-guess alignment. The bridge already forwards every field
above on `/jobs`, `/design`, and `/site`.
