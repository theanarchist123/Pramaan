# Theme: Seal & Ink on the public site (PG-16)  -  SPEC-DERIVED

The public web app used its own warm cream + orange palette; only the staff console used the Seal & Ink tokens. This maps the web app's
shadcn semantic variables (`--primary`, `--background`, `--card`, ...) onto `packages/ui/tokens.css`, so light and dark both come from the
tokens, and the contrast gate (`packages/ui/scripts/contrast.mjs`) now also checks text-on-primary (`--on-stamp`) and text on a selected row.

- Page: bond (cool paper) in light, deep ink-navy in dark. Accent / actions: stamp purple (lilac in dark). Verified: green. Alert: seal red.
- Hero wash: stamp glow + foil gold instead of saffron. Sector dots/charts use the sector palette.
- **Not done:** typography changes (still Fraunces headings + Inter body), the certificate and agent avatar palette (their own colours), a distinct
  hero composition, icon style, density, the Hindi pass, and component-level redesign (header, cards). This is a colour-system change, not a redesign.

## Second pass: composition (PG-16b)
- **Paper object** (`.paper-object` in globals.css): the Home proof table is a document lying on the desk: light in both themes, foil-gold edge,
  its own fixed inks (`--paper-verified/-seal/-stamp`, contrast-gated at 5.00 / 5.64 / 9.67 : 1). Descendants resolve `text-muted-foreground`
  etc. to paper inks, so existing components work inside it unchanged.
- Home headline larger and balanced; hero closed by a rule; step cards carry a 3px stamp rule and lift.
- Header: the current section is marked by a stamp underline, not a grey pill.
- Verify code boxes: found in the screenshot, they wrapped onto two rows (9 + 1). Now one flexible row that always fits, phone included.
- Still not done: typeface change, certificate palette, agent avatars, icon style, mobile review of every page, Hindi.
