# Theme: Seal & Ink on the public site (PG-16)  -  SPEC-DERIVED

The public web app used its own warm cream + orange palette; only the staff console used the Seal & Ink tokens. This maps the web app's
shadcn semantic variables (`--primary`, `--background`, `--card`, ...) onto `packages/ui/tokens.css`, so light and dark both come from the
tokens, and the contrast gate (`packages/ui/scripts/contrast.mjs`) now also checks text-on-primary (`--on-stamp`) and text on a selected row.

- Page: bond (cool paper) in light, deep ink-navy in dark. Accent / actions: stamp purple (lilac in dark). Verified: green. Alert: seal red.
- Hero wash: stamp glow + foil gold instead of saffron. Sector dots/charts use the sector palette.
- Before/after screenshots: `docs/design/before-after/`.
- **Not done:** typography changes (still Fraunces headings + Inter body), the certificate and agent avatar palette (their own colours), a distinct
  hero composition, icon style, density, the Hindi pass, and component-level redesign (header, cards). This is a colour-system change, not a redesign.
