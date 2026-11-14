import { api } from "@/lib/api";

const PAGE = 100; // the API's own maximum page size
const CEILING = 3000; // a safety stop: the directory never asks for more than this many in one go

/**
 * Every approved profile, newest first, fetched a page at a time. The list endpoint caps a page at 100, so a single call
 * silently hid everyone beyond the newest 100; this keeps asking until a page comes back short.
 * `onPage` gets the running list after each page so the screen can fill in while the rest loads.
 */
export async function fetchAllProfiles<T>(onPage?: (soFar: T[]) => void): Promise<T[]> {
  const all: T[] = [];
  for (let offset = 0; offset < CEILING; offset += PAGE) {
    const page = await api<T[]>(`/v1/profiles?limit=${PAGE}&offset=${offset}`, { auth: false });
    all.push(...page);
    onPage?.([...all]);
    if (page.length < PAGE) break;
  }
  return all;
}
