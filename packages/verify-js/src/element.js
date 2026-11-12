// <pramaan-verify code="PRM-XXXXXXXXXX" api="https://api.example.org" site="https://example.org"></pramaan-verify>
//
// Drop it on any page. It fetches the certificate and the registry's PUBLISHED keys, then checks the signature in the visitor's own browser
// with @pramaan/verify (it does not take the server's word for it), and asks the registry whether the certificate has since been revoked or replaced.
// All text is written with textContent: nothing from the certificate or the network is ever parsed as HTML.
import { verifyCertificate } from "./index.js";

const CSS = `
:host { display: block; font: 14px/1.45 system-ui, sans-serif; color: #1a1b3a; }
.box { border: 1px solid #d9dde8; border-radius: 12px; padding: 12px 14px; background: #fff; max-width: 34rem; }
.head { display: flex; gap: 8px; align-items: center; font-weight: 600; font-size: 16px; }
.dot { width: 10px; height: 10px; border-radius: 50%; background: #5a5f7a; flex: none; }
.ok .dot { background: #0b7a5e; } .bad .dot { background: #b8321b; } .warn .dot { background: #8a5a00; }
.ok .head { color: #0b7a5e; } .bad .head { color: #b8321b; } .warn .head { color: #8a5a00; }
.name { margin-top: 6px; font-size: 18px; font-weight: 600; }
.muted { color: #5a5f7a; font-size: 12.5px; margin-top: 4px; }
a { color: #4a2c8f; }
`;

export class PramaanVerify extends HTMLElement {
  static get observedAttributes() { return ["code", "api", "site"]; }

  connectedCallback() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    void this.#run();
  }

  attributeChangedCallback() {
    if (this.isConnected && this.shadowRoot) void this.#run();
  }

  #show(kind, title, lines = [], name = "") {
    const root = this.shadowRoot;
    root.replaceChildren();
    const style = document.createElement("style");
    style.textContent = CSS;
    const box = document.createElement("div");
    box.className = `box ${kind}`;
    box.setAttribute("role", "status");
    box.setAttribute("aria-live", "polite");
    const head = document.createElement("div");
    head.className = "head";
    const dot = document.createElement("span");
    dot.className = "dot";
    dot.setAttribute("aria-hidden", "true");
    const t = document.createElement("span");
    t.textContent = title;
    head.append(dot, t);
    box.append(head);
    if (name) {
      const n = document.createElement("div");
      n.className = "name";
      n.textContent = name;
      box.append(n);
    }
    for (const line of lines) {
      const p = document.createElement("div");
      p.className = "muted";
      if (line.href) {
        const a = document.createElement("a");
        a.href = line.href;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = line.text;
        p.append(a);
      } else {
        p.textContent = line;
      }
      box.append(p);
    }
    root.append(style, box);
  }

  async #run() {
    const code = (this.getAttribute("code") || "").trim().toUpperCase();
    const api = (this.getAttribute("api") || "").trim().replace(/\/+$/, "");
    const site = (this.getAttribute("site") || "").trim().replace(/\/+$/, "");
    if (!code || !api) return this.#show("warn", "Missing settings", ["Set the code and api attributes on <pramaan-verify>."]);
    this.#show("warn", "Checking...", ["Fetching the certificate and the registry's published keys."]);
    const link = site ? [{ href: `${site}/verify/${encodeURIComponent(code)}`, text: "See the full check on the registry" }] : [];
    try {
      const res = await fetch(`${api}/v1/certificates/${encodeURIComponent(code)}`);
      if (res.status === 404) return this.#show("bad", "Not found", [`The registry has no certificate with the code ${code}.`]);
      if (!res.ok) throw new Error(`certificate ${res.status}`);
      const cert = await res.json();
      const published = await (await fetch(`${api}/.well-known/pramaan-keys.json`)).json();
      const keys = Object.fromEntries((published.keys || []).map((k) => [k.kid, k.x]));
      const local = await verifyCertificate(cert, keys);
      const subject = String(cert.payload?.full_name ?? "");
      let live = null;
      try {
        const v = await fetch(`${api}/v1/verify/${encodeURIComponent(code)}`);
        if (v.ok) live = await v.json();
      } catch { /* the signature check still stands; revocation is reported as unchecked */ }
      if (!local.valid) {
        // A certificate the registry has withdrawn can legitimately fail the local check: erasing a person redacts their details, so the content
        // can no longer match its fingerprint. Say what the registry says. If the registry does NOT say revoked, a mismatch means it was altered.
        if (live?.revoked) return this.#show("bad", "Revoked", ["The registry has withdrawn this certificate. Its details may have been erased at the holder's request.", ...link]);
        return this.#show("bad", "Not valid", [local.reason, "This certificate does not match what the registry signed. Do not rely on it.", ...link], subject);
      }
      if (live?.revoked) return this.#show("bad", "Revoked", ["The signature is genuine, but the registry has withdrawn this certificate.", ...link], subject);
      if (live?.superseded_by) return this.#show("warn", "Genuine, but replaced", ["A newer certificate has replaced this one.", ...link], subject);
      this.#show(
        "ok", "Authentic",
        [
          `Signature checked in your browser against the registry's published key (${cert.key_id}).`,
          live ? "The registry also confirms it has not been revoked." : "Could not ask the registry about revocation just now.",
          ...link,
        ],
        subject,
      );
    } catch {
      this.#show("warn", "Could not check", ["The registry could not be reached. Nothing is claimed either way."]);
    }
  }
}

if (typeof customElements !== "undefined" && !customElements.get("pramaan-verify")) customElements.define("pramaan-verify", PramaanVerify);
