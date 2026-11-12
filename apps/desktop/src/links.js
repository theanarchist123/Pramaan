"use strict";
// Deep-link parsing, kept free of Electron so it can be tested on its own.
//
//   pramaan://verify/PRM-ABCDEFGHJK   -> /verify/PRM-ABCDEFGHJK
//   pramaan://profile/some-slug       -> /p/some-slug
//   pramaan://onboard | pramaan://directory
//
// A link comes from outside the app (a QR scan, an email, a web page), so it is untrusted: only these
// exact shapes are accepted and the result is ALWAYS a path on our own origin, never a URL.

const PROTOCOL = "pramaan";
const CODE_RE = /^PRM-[A-Z0-9]{6,12}$/i;
const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,80}$/;

function resolveDeepLink(raw) {
  if (typeof raw !== "string" || raw.length > 200) return null;
  let u;
  try {
    u = new URL(raw);
  } catch {
    return null;
  }
  if (u.protocol !== `${PROTOCOL}:` || u.username || u.password || u.port || u.search || u.hash) return null;
  let seg;
  try {
    seg = decodeURIComponent(u.pathname.replace(/^\//, ""));
  } catch {
    return null;
  }
  switch (u.hostname.toLowerCase()) {
    case "verify":
      return CODE_RE.test(seg) ? `/verify/${seg.toUpperCase()}` : null;
    case "profile":
      return SLUG_RE.test(seg) ? `/p/${seg}` : null;
    case "onboard":
      return seg === "" ? "/onboard" : null;
    case "directory":
      return seg === "" ? "/directory" : null;
    default:
      return null;
  }
}

function findDeepLink(argv) {
  return (argv || []).find((a) => typeof a === "string" && a.toLowerCase().startsWith(`${PROTOCOL}://`)) || null;
}

// Verifier mode: find ONE certificate code in text copied from anywhere (an email, a PDF, a chat). Clipboard text is untrusted, so only a
// code-shaped token is taken from it, and the result is a path on our own origin. Two different codes are ambiguous: refuse rather than guess.
function pathFromClipboard(text) {
  if (typeof text !== "string" || text.length > 5000) return null;
  const found = new Set((text.match(/\bPRM-[A-Z0-9]{6,12}\b/gi) || []).map((c) => c.toUpperCase()));
  return found.size === 1 ? `/verify/${[...found][0]}` : null;
}

module.exports = { PROTOCOL, resolveDeepLink, findDeepLink, pathFromClipboard };
