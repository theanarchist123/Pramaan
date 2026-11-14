# v3 motion catalogue (proposal; replaces M-01..M-28 once approved)

Rules: transform/opacity only; every effect has a reduced-motion variant (`lib/motion-preference.tsx`); effects fire on real events, never timers;
Devanagari text animates by word or `Intl.Segmenter` grapheme, never by code point; Rive and confetti are lazy-loaded; Motion via `LazyMotion`.

| ID | Moment | Trigger | Effect | Library |
|---|---|---|---|---|
| V-01 | Home search | typing / example chip | typewriter placeholder, spring re-order, tile tilt | Motion |
| V-02 | Saathi states | voice start, thinking, reply | listening / thinking / delighted | Rive |
| V-03 | Fact capture | `new_claims` in reply | fact flies from bubble to profile card | Motion |
| V-04 | Live certificate preview | each claim added | certificate assembles | Motion |
| V-05 | Completion meter | profile change | rolling percentage | NumberFlow |
| V-06 | Document check | upload + Lipik result | scan line, fields highlight, snap to claim | Motion + CSS |
| V-07 | Verification stamp | claim status change | stamp self-declared > public record > document verified; "with a reviewer" hold | Motion |
| V-08 | Certificate issued | certificate POST succeeds | confetti, 3D unfold, shine, QR pop | canvas-confetti + Motion |
| V-09 | Verify genuine | server valid | green ripple, signature draws | Motion |
| V-10 | Verify tampered | server invalid | red shake, changed letter highlighted | Motion |
| V-11 | Card to profile | click | shared-element morph | Motion layout |
| V-12 | Counts and map | data load | count-up | NumberFlow |
| V-13 | Hero emphasis | page load | one hand-drawn underline | Rough Notation |
| V-14 | Dock | hover / scroll | magnify, hide on scroll-down | Motion |
| V-15 | Staff lists | add / remove | smooth reflow only | auto-animate |

Test required: no "verified" visual appears before the server status says so (I-9).
