/**
 * Netlify serverless function — records a single page view for ORELIUS's daily
 * NXG funnel briefing. Privacy-preserving: it never stores a raw IP or
 * user-agent. Instead it derives a per-day, per-person hash so "people" can be
 * counted as distinct hashes with no personal data retained.
 *
 * The funnel front-end fires a tiny fire-and-forget beacon here on each page view
 * (see src/lib/visitTracker.ts). Writes go to the SAME Supabase project as leads,
 * using the service role (server-side only), so nothing is exposed to the browser.
 *
 * Reuses the env vars the lead function already uses — nothing new to configure:
 *   SUPABASE_URL
 *   SUPABASE_SERVICE_ROLE_KEY
 * Optional:
 *   VISIT_HASH_SALT   Extra salt for the visitor hash (any random string).
 */
import { createHash } from "node:crypto";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Content-Type": "application/json",
};

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const SALT = process.env.VISIT_HASH_SALT || "nxg-life-funnel";

function json(statusCode, obj) {
  return { statusCode, headers: CORS, body: JSON.stringify(obj) };
}

/** Coarse device class from the user-agent (never stored raw). */
function deviceFromUA(ua) {
  const s = (ua || "").toLowerCase();
  if (!s) return "unknown";
  if (/bot|crawler|spider|crawling|facebookexternalhit|slurp|bingpreview/.test(s)) return "bot";
  if (/ipad|tablet|playbook|silk|(android(?!.*mobile))/.test(s)) return "tablet";
  if (/mobi|iphone|ipod|android.*mobile|windows phone|blackberry|bb10|opera mini/.test(s)) return "mobile";
  return "desktop";
}

/** Today's date in Pacific (YYYY-MM-DD) so a person counts once per day. */
function pacificDay() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Los_Angeles" }).format(new Date());
}

export const handler = async (event) => {
  if (event.httpMethod === "OPTIONS") return { statusCode: 204, headers: CORS, body: "" };
  if (event.httpMethod !== "POST") return json(405, { ok: false });
  if (!SUPABASE_URL || !SUPABASE_KEY) return json(200, { ok: false, reason: "supabase_unset" });

  let body = {};
  try {
    body = JSON.parse(event.body || "{}");
  } catch {
    body = {};
  }

  const headers = event.headers || {};
  const ua = headers["user-agent"] || headers["User-Agent"] || "";
  const ip =
    headers["x-nf-client-connection-ip"] ||
    (headers["x-forwarded-for"] || "").split(",")[0].trim() ||
    "0.0.0.0";

  const device = deviceFromUA(ua);
  if (device === "bot") return json(200, { ok: true, skipped: "bot" }); // don't count bots as people

  const visitor_hash = createHash("sha256")
    .update(`${SALT}|${ip}|${ua}|${pacificDay()}`)
    .digest("hex")
    .slice(0, 32);

  const row = {
    path: (body.path || "/").toString().slice(0, 300),
    device,
    visitor_hash,
    referrer: (body.referrer || "").toString().slice(0, 500) || null,
  };

  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/page_views`, {
      method: "POST",
      headers: {
        apikey: SUPABASE_KEY,
        Authorization: `Bearer ${SUPABASE_KEY}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
      body: JSON.stringify(row),
    });
    if (!res.ok) {
      return json(200, { ok: false, status: res.status });
    }
  } catch {
    return json(200, { ok: false, reason: "insert_error" });
  }
  return json(200, { ok: true });
};
