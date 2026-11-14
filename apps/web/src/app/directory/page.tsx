"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { Loader2, Map as MapIcon, Network, Search, Users, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Constellation } from "@/components/directory/constellation";
import { IndiaMap } from "@/components/directory/india-map";
import { ResultCard, SectorChip } from "@/components/directory/result-card";
import { ResultRow } from "@/components/directory/result-row";
import { Shelf } from "@/components/directory/shelf";
import { api, ApiError } from "@/lib/api";
import { paletteFor } from "@/lib/certificate-art";
import { fetchAllProfiles } from "@/lib/profiles";
import {
  EXAMPLE_QUERIES, SECTORS,
  type GraphLink, type GraphNode, type MapStats, type SearchHit, type SearchResponse, type Summary,
} from "@/lib/directory-types";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type View = "people" | "network" | "map";

export default function Directory() {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [sector, setSector] = useState<string | null>(null);
  const [state, setState] = useState<string | null>(null);
  const [view, setView] = useState<View>("people");

  const [everyone, setEveryone] = useState<Summary[] | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [graph, setGraph] = useState<{ nodes: GraphNode[]; links: GraphLink[] } | null>(null);
  const [stats, setStats] = useState<MapStats | null>(null);
  const [picked, setPicked] = useState<GraphNode | null>(null);

  // A link such as /directory?sector=Science (from the home page's field tiles) starts with that field selected.
  useEffect(() => {
    try {
      const wanted = new URLSearchParams(window.location.search).get("sector");
      if (wanted && SECTORS.includes(wanted)) setSector(wanted);
      const asked = new URLSearchParams(window.location.search).get("q");
      if (asked?.trim()) {
        setQuery(asked);
        run(asked, wanted && SECTORS.includes(wanted) ? wanted : null, null);
      }
    } catch {
      /* no query string available: show everyone */
    }
  }, []);

  // Initial data: everyone, the relationship graph, and per-state counts.
  useEffect(() => {
    fetchAllProfiles<Summary>(setEveryone)
      .then(setEveryone)
      .catch(() => setEveryone((prev) => prev ?? []));
    api<{ nodes: GraphNode[]; links: GraphLink[] }>("/v1/graph", { auth: false }).then(setGraph).catch(() => {});
    api<MapStats>("/v1/stats/map", { auth: false }).then(setStats).catch(() => {});
  }, []);

  const run = useCallback(async (q: string, s: string | null, st: string | null) => {
    if (!q.trim()) {
      setResponse(null);
      return;
    }
    setSearching(true);
    try {
      const r = await api<SearchResponse>("/v1/search", {
        method: "POST", auth: false, json: { query: q.trim(), sector: s, state: st, limit: 18 },
      });
      setResponse(r);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }, []);

  // Re-run when a filter changes while a question is active.
  useEffect(() => {
    if (query.trim()) run(query, sector, state);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sector, state]);

  const filteredEveryone = useMemo(
    () => (everyone ?? []).filter((p) => (!sector || p.sector === sector) && (!state || p.state === state)),
    [everyone, sector, state],
  );
  const highlight = useMemo(() => (response ? new Set(response.results.map((r) => r.id)) : null), [response]);
  const inState = (s: string) => s === state || (state === "Ladakh" && s === "Jammu and Kashmir");
  const hasQuery = Boolean(response);
  const shown: (SearchHit | Summary)[] = hasQuery ? response!.results : filteredEveryone;
  const states = Object.keys(stats?.by_state ?? {}).sort();
  // With no question and no filter the page is a set of shelves, one per field, instead of one long undifferentiated list.
  const shelves: [string, Summary[]][] | null =
    hasQuery || sector || state || shown.length < 6
      ? null
      : Object.entries(
          filteredEveryone.reduce<Record<string, Summary[]>>((acc, p) => ((acc[p.sector] ??= []).push(p), acc), {}),
        ).sort((a, b) => b[1].length - a[1].length);

  return (
    <div className="-mt-28 md:-mt-16">
      <section data-nav-tone="on-dark" className="relative overflow-hidden bg-[#14152B] text-white">
        <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 size-96 rounded-full bg-[var(--brand)] opacity-20 blur-3xl" />
        <div aria-hidden className="pointer-events-none absolute -bottom-32 left-10 size-80 rounded-full bg-[#2447C9] opacity-25 blur-3xl" />
        <div className="relative mx-auto max-w-7xl px-4 pb-10 pt-36 md:pt-28">
          <div className="flex flex-wrap items-end justify-between gap-6">
            <div className="max-w-3xl">
              <h1 className="text-balance text-5xl leading-[1.02] md:text-7xl">{t("dir.title")}</h1>
              <p className="mt-4 max-w-2xl text-lg text-white/75">{t("dir.sub")}</p>
            </div>
            <dl className="flex gap-3 text-[#14152B]">
              {[
                [Math.max(stats?.total ?? 0, everyone?.length ?? 0), "people"],
                [Object.keys(stats?.by_sector ?? {}).length, "fields"],
                [states.length, "states"],
              ].map(([n, label]) => (
                <div key={String(label)} className="min-w-24 rounded-2xl bg-[var(--brand)] px-4 py-3">
                  <dd className="font-display text-3xl font-extrabold tabular-nums leading-none">{n}</dd>
                  <dt className="mt-1 text-xs font-semibold">{label}</dt>
                </div>
              ))}
            </dl>
          </div>

          <form
            className="mt-8 flex max-w-4xl gap-2 rounded-full border-2 border-white bg-white p-1.5 shadow-[0_6px_0_var(--brand)]"
            onSubmit={(e) => {
              e.preventDefault();
              run(query, sector, state);
              setView("people");
            }}
          >
            <Search aria-hidden className="ml-4 hidden size-5 shrink-0 self-center text-[#4B4E68] sm:block" />
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                if (!e.target.value.trim()) setResponse(null);
              }}
              placeholder={t("dir.placeholder")}
              className="min-w-0 flex-1 bg-transparent px-3 py-3 text-base text-[#14152B] placeholder:text-[#5E6280] focus:outline-none"
              aria-label={t("dir.search")}
            />
            <button type="submit" disabled={searching || !query.trim()} className="inline-flex min-w-28 items-center justify-center rounded-full bg-[#14152B] px-6 text-base font-semibold text-white disabled:opacity-50">
              {searching ? <Loader2 className="animate-spin" /> : t("dir.searchBtn")}
            </button>
          </form>

          {!hasQuery && (
            <div className="mt-4 flex flex-wrap gap-2">
              {EXAMPLE_QUERIES.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => {
                    setQuery(q);
                    run(q, sector, state);
                    setView("people");
                  }}
                  className="rounded-full border border-white/30 px-3.5 py-1.5 text-left text-sm text-white/85 transition-colors hover:bg-white/10"
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          <div className="mt-8 flex flex-wrap items-center gap-2" role="group" aria-label="Fields">
            {SECTORS.filter((sx) => (stats?.by_sector?.[sx] ?? 0) > 0).map((sx, i) => {
              const k = (i % 6) + 1;
              const on = sector === sx;
              return (
                <button
                  key={sx}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setSector(on ? null : sx)}
                  className={cn("inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-semibold transition-transform hover:-translate-y-0.5", on && "ring-2 ring-white ring-offset-2 ring-offset-[#14152B]")}
                  style={{ background: `var(--tile${k})`, color: `var(--tile${k}i)` }}
                >
                  {sx} <span className="tabular-nums">{stats?.by_sector?.[sx]}</span>
                </button>
              );
            })}
            <label className="sr-only" htmlFor="state-filter">State</label>
            <select
              id="state-filter"
              value={state ?? ""}
              onChange={(e) => setState(e.target.value || null)}
              className="h-9 rounded-full border border-white/30 bg-transparent px-3 text-sm text-white"
            >
              <option value="" className="text-black">{t("dir.allStates")}</option>
              {states.map((st) => (
                <option key={st} value={st} className="text-black">{st} ({stats?.by_state[st]})</option>
              ))}
            </select>
            {(sector || state) && (
              <button type="button" onClick={() => { setSector(null); setState(null); }} className="inline-flex items-center gap-1 text-sm text-white/80 hover:text-white">
                <X className="size-4" /> {t("dir.clear")}
              </button>
            )}
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-7xl px-4 pb-10 pt-6">
      <div className="mt-6 flex items-center justify-between gap-3 border-b border-border">
        <div role="tablist" aria-label="Views" className="flex">
          {([
            ["people", t("dir.people"), Users],
            ["network", t("dir.network"), Network],
            ["map", t("dir.map"), MapIcon],
          ] as const).map(([v, label, Icon]) => (
            <button
              key={v}
              role="tab"
              aria-selected={view === v}
              onClick={() => setView(v)}
              className={cn(
                "-mb-px inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                view === v ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="size-4" /> {label}
            </button>
          ))}
        </div>
        <p className="hidden text-xs text-muted-foreground sm:block" aria-live="polite">
          {hasQuery
            ? `${response!.results.length} result${response!.results.length === 1 ? "" : "s"} · ${response!.took_ms} ms · ${response!.embedder === "fastembed" ? "semantic" : "keyword"} match`
            : `${filteredEveryone.length} ${filteredEveryone.length === 1 ? "person" : "people"}`}
        </p>
      </div>

      {response && (response.plan.state || response.plan.sector || response.relaxed) && (
        <p className="mt-3 rounded-xl bg-indigo-soft/60 px-3 py-2 text-sm text-indigo">
          {response.relaxed
            ? "No exact match for those filters, so these are the closest people instead."
            : `Understood your question${response.plan.state ? ` as people in ${response.plan.state}` : ""}${response.plan.sector ? `, leaning towards ${response.plan.sector}` : ""}.`}
        </p>
      )}

      <div className="mt-6">
        {view === "people" && (
          everyone === null || searching ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-44 rounded-2xl" />)}
            </div>
          ) : shown.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border p-12 text-center text-muted-foreground">
              <p className="font-medium text-foreground">{t("dir.none")}</p>
              <p className="mt-1 text-sm">{t("dir.noneHint")}</p>
            </div>
          ) : (
            shelves ? (
              <div className="space-y-10">
                {shelves.map(([name, people]) => (
                  <Shelf key={name} name={name} people={people} onSeeAll={() => setSector(name)} />
                ))}
              </div>
            ) : hasQuery ? (
              <ol className="space-y-3" aria-label="Results, best match first">
                {(shown as SearchHit[]).map((h, i) => (
                  <ResultRow key={h.id} hit={h} rank={i + 1} />
                ))}
              </ol>
            ) : (
              <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <AnimatePresence mode="popLayout">
                  {shown.map((h, i) => (
                    <ResultCard key={h.id} hit={h as SearchHit} index={i} />
                  ))}
                </AnimatePresence>
              </ul>
            )
          )
        )}

        {view === "network" && (
          <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
            {graph ? (
              <Constellation
                nodes={graph.nodes.filter((n) => (!sector || n.sector === sector) && (!state || inState(n.state)))}
                links={graph.links}
                highlight={highlight}
                onSelect={setPicked}
                selectedId={picked?.id}
              />
            ) : (
              <Skeleton className="h-[34rem] rounded-2xl" />
            )}
            <aside className="rounded-2xl border border-border bg-card p-4" aria-live="polite">
              <AnimatePresence mode="wait">
                {picked ? (
                  <motion.div key={picked.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                    <SectorChip sector={picked.sector} />
                    <p className="mt-2 font-display text-xl font-semibold">{picked.name}</p>
                    <p className="text-sm text-muted-foreground">{picked.headline}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{picked.state}</p>
                    <p className="mt-4 text-xs font-medium">Connected to</p>
                    <ul className="mt-1 space-y-1.5 text-xs">
                      {(graph?.links ?? [])
                        .filter((l) => l.source === picked.id || l.target === picked.id)
                        .sort((a, b) => b.weight - a.weight)
                        .slice(0, 6)
                        .map((l, i) => {
                          const other = graph!.nodes.find((n) => n.id === (l.source === picked.id ? l.target : l.source));
                          return (
                            <li key={i}>
                              <button className="text-left hover:text-primary" onClick={() => other && setPicked(other)}>
                                <span className="font-medium">{other?.name}</span>
                                <span className="block text-muted-foreground">{l.why}</span>
                              </button>
                            </li>
                          );
                        })}
                    </ul>
                    <Button className="mt-4 w-full" render={<Link href={`/p/${picked.slug}`} />} nativeButton={false}>View profile</Button>
                  </motion.div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Each dot is a person, coloured by field. Lines connect people who share an institution, a city, or a field in the same state.
                    {highlight && " Your search results are lit up."} Click a dot to explore.
                  </p>
                )}
              </AnimatePresence>
            </aside>
          </div>
        )}

        {view === "map" && (
          <div className="grid items-start gap-6 lg:grid-cols-[1fr_20rem]">
            <IndiaMap stats={stats} selected={state} onSelect={setState} />
            <aside className="rounded-2xl border border-border bg-card p-4">
              <p className="font-display text-xl font-semibold">{state ?? "All of India"}</p>
              <p className="text-sm text-muted-foreground">
                {state ? `${stats?.by_state[state] ?? 0} member(s)` : `${stats?.total ?? 0} verified members`} — click a state to filter.
              </p>
              <ul className="mt-4 space-y-2">
                {Object.entries(stats?.by_sector ?? {}).sort((a, b) => b[1] - a[1]).map(([s]) => {
                  const n = (stats?.by_state_sector ?? [])
                    .filter((x) => x.sector === s && (!state || x.state === state))
                    .reduce((a, x) => a + x.count, 0);
                  if (!n) return null;
                  const total = state ? stats?.by_state[state] ?? 1 : stats?.total ?? 1;
                  return (
                    <li key={s}>
                      <div className="flex justify-between text-xs"><span>{s}</span><span className="tabular-nums text-muted-foreground">{n}</span></div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                        <div className="h-full rounded-full" style={{ width: `${(n / total) * 100}%`, background: paletteFor(s).primary }} />
                      </div>
                    </li>
                  );
                })}
              </ul>
              <Button variant="outline" className="mt-4 w-full" onClick={() => setView("people")}>
                See these people
              </Button>
            </aside>
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
