/** The only API paths the staff console may forward (least privilege). Anything else is refused before it leaves the console. */
const ALLOWED = [/^v1\/admin\//, /^v1\/auth\/mfa\//, /^v1\/search$/, /^v1\/images\/sector\//];

export function isAllowed(path: string): boolean {
  if (path.includes("..") || path.includes("//") || path.includes("\\") || path.includes("%")) return false; // no tricks around the list
  return ALLOWED.some((r) => r.test(path));
}

/** The API origin the console forwards to, read when the request arrives (not when the site was built). Empty when it is not set. */
export function apiTarget(env: Record<string, string | undefined> = process.env): string {
  return (env.API_INTERNAL_URL ?? "").trim().replace(/\/+$/, "");
}
