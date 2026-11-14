"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

interface Report {
  cases: number; approved: number; rejected: number; enough_history: boolean; note: string; current_threshold: number; floor: number;
  by_reason_code: { reason_code: string; cases: number; approved: number; rejected: number; approval_rate: number }[];
  shadow: { threshold: number; would_auto_approve: number; humans_rejected: number; humans_rejected_share: number }[];
}

/**
 * How people actually decided past escalated cases, and what a lower auto-approve threshold WOULD have done to them. A report: it changes nothing.
 * The threshold is a governed setting that two people change, never below the floor.
 */
export default function CalibrationPage() {
  const router = useRouter();
  const [r, setR] = useState<Report | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Report>("/v1/admin/calibration")
      .then(setR)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) router.push("/login");
        else setError(e instanceof Error ? e.message : "Couldn't load the report");
      });
  }, [router]);

  const pct = (x: number) => `${Math.round(x * 100)}%`;
  return (
    <main>
      <div className="row"><h1 className="grow">Calibration</h1></div>
      {error && <p className="err" role="alert">{error}</p>}
      {!r && !error && <p className="muted">Loading...</p>}
      {r && (
        <>
          <p className="panel" role="note">{r.note}</p>
          <div className="tiles">
            <div className="tile"><div className="muted">Closed cases</div><div className="tile-n">{r.cases}</div><div className="muted">{r.approved} approved, {r.rejected} rejected</div></div>
            <div className="tile"><div className="muted">Auto-approve threshold</div><div className="tile-n">{pct(r.current_threshold)}</div><div className="muted">floor {pct(r.floor)}</div></div>
          </div>

          <section className="panel" aria-label="By reason">
            <strong>How people decided, by why the case was escalated</strong>
            {r.by_reason_code.length === 0 ? <p className="muted">No closed cases yet.</p> : (
              <table>
                <thead><tr><th>Reason</th><th>Cases</th><th>Approved</th><th>Rejected</th><th>Approval rate</th></tr></thead>
                <tbody>{r.by_reason_code.map((x) => (
                  <tr key={x.reason_code}><td><span className="chip">{x.reason_code}</span></td><td>{x.cases}</td><td>{x.approved}</td><td>{x.rejected}</td><td>{pct(x.approval_rate)}</td></tr>
                ))}</tbody>
              </table>
            )}
          </section>

          <section className="panel" aria-label="Shadow run">
            <strong>If the threshold had been lower</strong>
            <p className="muted">Past escalated cases that would have been approved without a person, and how many of those people actually rejected.</p>
            <table>
              <thead><tr><th>Threshold</th><th>Would auto-approve</th><th>People rejected</th><th>Share</th></tr></thead>
              <tbody>{r.shadow.map((x) => (
                <tr key={x.threshold}><td>{pct(x.threshold)}</td><td>{x.would_auto_approve}</td><td className={x.humans_rejected > 0 ? "warn" : ""}>{x.humans_rejected}</td><td>{x.would_auto_approve ? pct(x.humans_rejected_share) : "none"}</td></tr>
              ))}</tbody>
            </table>
          </section>
        </>
      )}
    </main>
  );
}
