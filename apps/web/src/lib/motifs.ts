// The certificate's motif vocabulary, drawn as vector paths (AGT-04, spec 9.3). Every name here must exist in backend/app/agents/chitrakar.py (MOTIFS);
// a backend test checks both directions. All motifs are abstract geometry: no faces, flags, logos, text, people or religious imagery.
// Drawing is deterministic from (motif, seed): the same signed brief always renders the same pattern, offline.
import { rngFromHex } from "@/lib/certificate-art";

export type Kernel = "rings" | "rays" | "arcs" | "waves" | "grid" | "dots" | "spiral" | "steps";
export interface MotifSpec { kernel: Kernel; a: number; b: number }

export const MOTIF_KERNEL: Record<string, MotifSpec> = {
  // Science
  orbit_rings: { kernel: "rings", a: 5, b: 0.7 }, lattice_cells: { kernel: "grid", a: 7, b: 0 }, wave_interference: { kernel: "waves", a: 4, b: 2 },
  helix_strands: { kernel: "waves", a: 3, b: 4 }, spectral_bands: { kernel: "steps", a: 9, b: 0 },
  // Technology
  circuit_traces: { kernel: "steps", a: 7, b: 1 }, node_graph: { kernel: "dots", a: 14, b: 1 }, binary_grid: { kernel: "grid", a: 9, b: 1 },
  signal_arcs: { kernel: "arcs", a: 6, b: 0 }, hex_mesh: { kernel: "grid", a: 6, b: 2 },
  // Healthcare
  pulse_line: { kernel: "waves", a: 2, b: 6 }, cell_rings: { kernel: "rings", a: 4, b: 0.5 }, section_rings: { kernel: "rings", a: 7, b: 0.9 },
  rod_lines: { kernel: "rays", a: 10, b: 0 }, heartbeat_wave: { kernel: "waves", a: 3, b: 7 },
  // Education
  open_book_arcs: { kernel: "arcs", a: 4, b: 1 }, ladder_steps: { kernel: "steps", a: 6, b: 2 }, growth_rings: { kernel: "rings", a: 8, b: 0.6 },
  chalk_lines: { kernel: "rays", a: 14, b: 1 }, stacked_arches: { kernel: "arcs", a: 5, b: 2 },
  // Arts & Culture
  woven_threads: { kernel: "grid", a: 8, b: 3 }, brush_arcs: { kernel: "arcs", a: 3, b: 3 }, rangoli_dots: { kernel: "dots", a: 20, b: 0 },
  paisley_curves: { kernel: "spiral", a: 3, b: 1 }, mosaic_tiles: { kernel: "grid", a: 5, b: 4 },
  // Literature
  verse_lines: { kernel: "steps", a: 11, b: 3 }, quill_strokes: { kernel: "arcs", a: 7, b: 4 }, page_folds: { kernel: "steps", a: 5, b: 4 },
  ink_ripples: { kernel: "rings", a: 6, b: 0.8 }, scroll_curls: { kernel: "spiral", a: 4, b: 2 },
  // Sports
  track_lanes: { kernel: "rings", a: 6, b: 0.4 }, motion_chevrons: { kernel: "rays", a: 8, b: 2 }, finish_lines: { kernel: "steps", a: 8, b: 5 },
  speed_arcs: { kernel: "arcs", a: 8, b: 5 }, court_lines: { kernel: "grid", a: 4, b: 5 },
  // Business
  ledger_grid: { kernel: "grid", a: 10, b: 6 }, growth_steps: { kernel: "steps", a: 6, b: 6 }, trade_routes: { kernel: "arcs", a: 5, b: 6 },
  balance_arcs: { kernel: "arcs", a: 2, b: 7 }, stacked_bars: { kernel: "steps", a: 10, b: 7 },
  // Public Service
  pillar_arches: { kernel: "arcs", a: 6, b: 8 }, chain_links: { kernel: "rings", a: 9, b: 0.3 }, compass_rays: { kernel: "rays", a: 16, b: 3 },
  bridge_spans: { kernel: "arcs", a: 4, b: 9 }, scale_lines: { kernel: "steps", a: 7, b: 8 },
  // Law
  balance_beams: { kernel: "rays", a: 6, b: 4 }, column_lines: { kernel: "steps", a: 9, b: 9 }, ledger_rules: { kernel: "grid", a: 12, b: 7 },
  interlocked_rings: { kernel: "rings", a: 5, b: 0.2 }, level_lines: { kernel: "steps", a: 12, b: 10 },
  // Media
  broadcast_arcs: { kernel: "arcs", a: 9, b: 10 }, frame_grids: { kernel: "grid", a: 3, b: 8 }, signal_waves: { kernel: "waves", a: 5, b: 3 },
  lens_rings: { kernel: "rings", a: 3, b: 0.85 }, column_bars: { kernel: "steps", a: 8, b: 11 },
  // Social Work
  linked_hands_lines: { kernel: "rays", a: 12, b: 5 }, shelter_arches: { kernel: "arcs", a: 3, b: 11 }, ripple_rings: { kernel: "rings", a: 10, b: 0.5 },
  seed_dots: { kernel: "dots", a: 18, b: 2 }, bridge_curves: { kernel: "spiral", a: 2, b: 3 },
  // Agriculture
  furrow_lines: { kernel: "steps", a: 13, b: 12 }, grain_sprays: { kernel: "rays", a: 18, b: 6 }, terrace_contours: { kernel: "rings", a: 7, b: 0.55 },
  rain_arcs: { kernel: "arcs", a: 10, b: 12 }, // seed_dots is shared with Social Work
  // Energy
  turbine_blades: { kernel: "rays", a: 3, b: 7 }, solar_petals: { kernel: "rays", a: 12, b: 8 }, grid_lines: { kernel: "grid", a: 11, b: 9 },
  flow_arcs: { kernel: "arcs", a: 7, b: 13 }, spark_rays: { kernel: "rays", a: 20, b: 9 },
  // Other
  concentric_rings: { kernel: "rings", a: 9, b: 0.75 }, rosette_petals: { kernel: "rays", a: 14, b: 10 }, wave_lines: { kernel: "waves", a: 6, b: 1 },
  dot_lattice: { kernel: "dots", a: 24, b: 3 }, radial_rays: { kernel: "rays", a: 24, b: 11 },
};

export const SYMMETRY_FOLDS: Record<string, number> = { radial_6: 6, radial_8: 8, radial_12: 12, mirror: 2 };
export const DENSITY_SCALE: Record<string, number> = { low: 0.7, medium: 1, high: 1.4 };

const f = (n: number) => n.toFixed(1);

/** One fold's worth of path data inside a 100-unit radius; the caller rotates it into the symmetry. Pure and deterministic. */
export function motifPath(name: string, seed: string, density: string): string {
  const spec = MOTIF_KERNEL[name];
  if (!spec) return ""; // an unknown name draws nothing: the renderer never invents art
  const rnd = rngFromHex(seed + name);
  const n = Math.max(2, Math.round(spec.a * (DENSITY_SCALE[density] ?? 1)));
  const jitter = (rnd() - 0.5) * 3;
  const out: string[] = [];
  switch (spec.kernel) {
    case "rings":
      for (let i = 1; i <= n; i++) {
        const r = (i / n) * 96;
        out.push(`M${f(r)} 0A${f(r)} ${f(r * (spec.b > 1 ? 1 : 0.4 + spec.b * 0.6))} 0 0 1 ${f(-r * 0.5)} ${f(r * 0.86)}`);
      }
      break;
    case "rays":
      for (let i = 0; i < n; i++) {
        const a = (i / n) * 0.6;
        out.push(`M${f(14 * Math.cos(a))} ${f(14 * Math.sin(a))}L${f(98 * Math.cos(a + jitter / 50))} ${f(98 * Math.sin(a + jitter / 50))}`);
      }
      break;
    case "arcs":
      for (let i = 1; i <= n; i++) {
        const r = 14 + (i / n) * 82;
        out.push(`M${f(r)} 0A${f(r)} ${f(r)} 0 0 1 ${f(r * Math.cos(1.0 + spec.b * 0.05))} ${f(r * Math.sin(1.0 + spec.b * 0.05))}`);
      }
      break;
    case "waves":
      for (let k = 0; k < Math.max(2, Math.round(spec.a * 0.8)); k++) {
        const r = 24 + k * (70 / Math.max(2, spec.a));
        let d = `M${f(r)} 0`;
        for (let t = 1; t <= 24; t++) {
          const ang = (t / 24) * 0.9;
          const rr = r + Math.sin(t * (spec.b + 1) * 0.7 + jitter) * 5;
          d += `L${f(rr * Math.cos(ang))} ${f(rr * Math.sin(ang))}`;
        }
        out.push(d);
      }
      break;
    case "grid":
      for (let i = -n; i <= n; i += 2) out.push(`M${f((i / n) * 90)} -90L${f((i / n) * 90)} 90`, `M-90 ${f((i / n) * 90)}L90 ${f((i / n) * 90)}`);
      break;
    case "dots": {
      for (let i = 0; i < n; i++) {
        const a = rnd() * 0.9, r = 18 + rnd() * 78;
        out.push(`M${f(r * Math.cos(a) - 1.4)} ${f(r * Math.sin(a))}a1.4 1.4 0 1 0 2.8 0a1.4 1.4 0 1 0 -2.8 0`);
      }
      break;
    }
    case "spiral": {
      let d = "M12 0";
      for (let t = 1; t <= 60; t++) { const a = t * 0.18 * (1 + spec.a * 0.05); const r = 12 + t * 1.4; d += `L${f(r * Math.cos(a))} ${f(r * Math.sin(a))}`; }
      out.push(d);
      break;
    }
    case "steps":
      for (let i = 0; i < n; i++) { const y = -80 + (i / n) * 160; out.push(`M-80 ${f(y)}H${f(-80 + 40 + (i % 3) * 30)}V${f(y + 160 / n)}H80`); }
      break;
  }
  return out.join("");
}
