# v3 tokens (proposal for packages/ui/tokens.css)

Keep existing token names (the shadcn mapping in `apps/web/src/app/globals.css` depends on them); change values; add `--brand`.
The contrast gate (`pnpm --filter @pramaan/ui test`) must pass; fix colours, never the gate. Values below are from the approved mock and are NOT yet checked by the gate.

| Token role | Light | Dark |
|---|---|---|
| ground (`--bond`) | #FFFFFF | #0F1020 |
| soft area | #FFF4D6 | #26220F |
| ink / primary (`--ink`, primary button) | #14152B | #F1F2FB (button: marigold on ink) |
| muted ink | #4B4E68 | #A9ADC9 |
| brand (`--brand`, new) | #FFB81C | #FFB81C |
| verified / tint | #0B7F57 / #D9F5E8 | #4FD1A0 / #10382B |
| public record / tint | #2447C9 / #E2E9FF | #8FA8FF / #1B2552 |
| self-declared / tint | #5E6280 / #ECEDF4 | #B3B6D0 / #272947 |
| rule | #E3E5EF | #2A2C4A |

Tile pairs c1..c6 (bg / text): blue #E8F0FF/#2447C9, coral #FFE3DC/#B7351A, green #DDF5E6/#0B7F57, violet #F1E4FF/#7B35C4, amber #FFF0C2/#8A5A00, teal #DAF3F6/#0A7585; dark variants in the mock.

Type: Bricolage Grotesque (headings), Inter (body), Noto Sans Devanagari (Hindi). Radii: pill, 20-26px cards. Hero objects: 8px offset ink shadow.
