/** Empty/unset allow-list means everyone may sign in. Domains are comma-separated, e.g. "live.concordia.ca,concordia.ca". */
export function emailAllowed(email: string | null | undefined, allowList: string | undefined): boolean {
  const domains = (allowList ?? "").split(",").map((d) => d.trim().toLowerCase()).filter(Boolean);
  if (domains.length === 0) return true;
  const domain = email?.toLowerCase().split("@")[1];
  return !!domain && domains.includes(domain);
}
