export class SourceError extends Error {}

/** GET JSON, retrying network errors, 429 and 5xx. Error messages never include the URL (it may carry keys). */
export async function getJson(url: string, retries = 3, timeoutMs = 20_000): Promise<unknown> {
  let last = "unknown error";
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
      if (res.ok) {
        try {
          return await res.json();
        } catch {
          throw new SourceError("response was not valid JSON");
        }
      }
      last = `HTTP ${res.status}`;
      if (res.status < 500 && res.status !== 429) break;
    } catch (e) {
      if (e instanceof SourceError) throw e;
      last = e instanceof Error ? e.name : "network error";
    }
    if (attempt < retries) await new Promise((r) => setTimeout(r, 2 ** (attempt - 1) * 1000));
  }
  throw new SourceError(`request failed (${last})`);
}
