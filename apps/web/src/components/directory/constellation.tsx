"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useTheme } from "next-themes";
import { paletteFor } from "@/lib/certificate-art";
import type { GraphLink, GraphNode } from "@/lib/directory-types";

/* eslint-disable @typescript-eslint/no-explicit-any */
type GraphHandle = { zoomToFit: (ms?: number, padding?: number, nodeFilter?: (n: any) => boolean) => void; d3Force: (name: string) => any };

// Canvas library: browser-only. next/dynamic doesn't forward refs, so a thin wrapper hands the
// graph handle back through `fgRef` (needed to zoom-to-fit) and tightens the layout.
const ForceGraph2D = dynamic(
  async () => {
    const Graph = (await import("react-force-graph-2d")).default as any;
    return function GraphWithHandle({ fgRef, ...props }: any) {
      return (
        <Graph
          ref={(r: GraphHandle | null) => {
            fgRef.current = r;
            // Weaker repulsion keeps unconnected clusters close enough to read as one picture.
            r?.d3Force("charge")?.strength(-30);
            r?.d3Force("link")?.distance?.(28);
          }}
          {...props}
        />
      );
    };
  },
  { ssr: false },
) as unknown as React.ComponentType<Record<string, any>>;

const LINK_LABEL: Record<GraphLink["type"], string> = {
  alumni: "Shared institution", org: "Same organisation", city: "Same city", sector: "Same field & state", collab: "Stated working connection",
};

type FGNode = GraphNode & { x?: number; y?: number };

export function Constellation({
  nodes, links, highlight, onSelect, selectedId,
}: {
  nodes: GraphNode[];
  links: GraphLink[];
  highlight: Set<string> | null;
  onSelect: (n: GraphNode | null) => void;
  selectedId?: string | null;
}) {
  const { resolvedTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 560 });
  const [hover, setHover] = useState<string | null>(null);
  const fgRef = useRef<GraphHandle | null>(null);
  // People with no connections drift far from everyone else; fitting the view to them would shrink the real network into a corner. Fit to the connected people.
  const connected = useRef<Set<string>>(new Set());
  const fit = () => {
    const ok = connected.current;
    fgRef.current?.zoomToFit(500, 60, ok.size >= 3 ? (n: any) => ok.has(n.id) : undefined);
  };

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: Math.max(460, Math.min(640, el.clientWidth * 0.62)) }));
    ro.observe(el);
    setSize({ w: el.clientWidth, h: Math.max(460, Math.min(640, el.clientWidth * 0.62)) });
    return () => ro.disconnect();
  }, []);

  // Structural ties (shared institution) pull tighter than weak ones (same sector/state).
  const data = useMemo(() => ({ nodes: nodes.map((n) => ({ ...n })), links: links.map((l) => ({ ...l })) }), [nodes, links]);
  const neighbours = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const l of links) {
      (m.get(l.source) ?? m.set(l.source, new Set()).get(l.source)!).add(l.target);
      (m.get(l.target) ?? m.set(l.target, new Set()).get(l.target)!).add(l.source);
    }
    connected.current = new Set(m.keys());
    return m;
  }, [links]);

  useEffect(() => {
    const t = setTimeout(fit, 900);
    return () => clearTimeout(t);
  }, [nodes.length, size.w]);

  const focus = hover ?? selectedId ?? null;
  const lit = (id: string) =>
    focus ? id === focus || neighbours.get(focus)?.has(id) === true : highlight ? highlight.has(id) : true;

  return (
    <div ref={box} className="relative w-full overflow-hidden rounded-2xl border border-border bg-card" role="img"
      aria-label="Network of registry members, linked by shared institutions, cities and fields">
      <ForceGraph2D
        fgRef={fgRef}
        onEngineStop={fit}
        width={size.w}
        height={size.h}
        graphData={data}
        backgroundColor="rgba(0,0,0,0)"
        cooldownTicks={140}
        nodeRelSize={5}
        linkWidth={(l: any) => (["alumni", "collab"].includes((l as unknown as GraphLink).type) ? 1.6 : 0.5)}
        linkColor={(l: any) => {
          const s = (l as unknown as { source: FGNode }).source, t = (l as unknown as { target: FGNode }).target;
          const on = !focus || s.id === focus || t.id === focus;
          const base = ["alumni", "collab"].includes((l as unknown as GraphLink).type) ? (dark ? "200,200,255" : "60,60,140") : dark ? "180,180,180" : "120,120,120";
          return `rgba(${base},${on ? (["alumni", "collab"].includes((l as unknown as GraphLink).type) ? 0.55 : 0.18) : 0.04})`;
        }}
        linkLabel={(l: any) => LINK_LABEL[(l as unknown as GraphLink).type] + " — " + (l as unknown as GraphLink).why}
        onNodeHover={(n: any) => setHover(n ? (n as FGNode).id : null)}
        onNodeClick={(n: any) => onSelect(n as GraphNode)}
        onBackgroundClick={() => onSelect(null)}
        d3VelocityDecay={0.3}
        nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, scale: number) => {
          const n = node as FGNode;
          const c = paletteFor(n.sector);
          const on = lit(n.id);
          const r = (n.id === focus ? 8 : 5.5);
          ctx.globalAlpha = on ? 1 : 0.22;
          ctx.beginPath();
          ctx.arc(n.x!, n.y!, r, 0, 2 * Math.PI);
          ctx.fillStyle = c.primary;
          ctx.fill();
          ctx.lineWidth = n.id === selectedId ? 2.5 : 1.2;
          ctx.strokeStyle = n.id === selectedId ? (dark ? "#fff" : "#111") : c.ink;
          ctx.stroke();
          if (on && (scale > 1.4 || n.id === focus)) {
            ctx.font = `${n.id === focus ? 600 : 400} ${11 / Math.max(scale, 0.9)}px Inter, sans-serif`;
            ctx.textAlign = "center";
            ctx.fillStyle = dark ? "#eee" : "#222";
            ctx.fillText(n.name, n.x!, n.y! + r + 10 / Math.max(scale, 0.9));
          }
          ctx.globalAlpha = 1;
        }}
        nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
          const n = node as FGNode;
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(n.x!, n.y!, 9, 0, 2 * Math.PI);
          ctx.fill();
        }}
      />
      <div className="pointer-events-none absolute bottom-3 left-3 flex flex-wrap gap-x-3 gap-y-1 rounded-lg bg-background/80 p-2 text-[11px] backdrop-blur">
        {Array.from(new Set(nodes.map((n) => n.sector))).map((s) => (
          <span key={s} className="inline-flex items-center gap-1">
            <span className="size-2 rounded-full" style={{ background: paletteFor(s).primary }} /> {s}
          </span>
        ))}
      </div>
      <p className="pointer-events-none absolute right-3 top-3 max-w-[14rem] rounded-lg bg-background/80 p-2 text-[11px] text-muted-foreground backdrop-blur">
        Thick lines: shared institution. Hover a person to see who they connect to; click for details.
      </p>
    </div>
  );
}
