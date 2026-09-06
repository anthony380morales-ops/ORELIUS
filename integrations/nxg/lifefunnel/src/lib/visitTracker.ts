/**
 * visitTracker — fires a tiny, fire-and-forget beacon to the same-origin Netlify
 * function on each page view so ORELIUS can report real people + device counts.
 *
 * Privacy-preserving: the browser sends only the path + referrer. The server
 * derives a per-day hash from IP/UA and never stores them (see
 * netlify/functions/track-view.mjs). Safe to call on every route change; failures
 * are swallowed so tracking can never affect the funnel UX.
 */
const ENDPOINT = "/.netlify/functions/track-view";

export function recordVisit(path?: string): void {
  try {
    const payload = JSON.stringify({
      path: path || window.location.pathname,
      referrer: document.referrer || "",
    });

    // Prefer sendBeacon (survives navigation); fall back to a keepalive fetch.
    if (navigator.sendBeacon) {
      navigator.sendBeacon(ENDPOINT, new Blob([payload], { type: "application/json" }));
      return;
    }
    void fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      keepalive: true,
    });
  } catch {
    /* never let analytics break the page */
  }
}
