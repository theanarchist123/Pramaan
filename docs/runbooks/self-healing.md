# Self-healing, without unsafe auto-deploys (AGT-13)

What is automatic: noticing. What is never automatic: changing, merging, deploying.

1. **Nigrani notices.** `python -m app.cli nigrani-scan` (run it from cron every 10 minutes, or press "Scan now" on the Incidents page) counts failed agent runs in the
   last hour. At least 5 failures and at least 30% of that workflow's runs, with the same kind of error, opens ONE incident. Switch-offs, budget stops and refusals are not counted.
2. **The fixer proposes.** "Propose a patch" on an incident asks the model for a small unified diff. It is stored on the incident only if it applies to the real files,
   is under 4,000 characters, creates or deletes nothing, and touches only application code under `backend/app/`: never signing, keys, the code guard, the sandbox, Prahari,
   auth/RBAC, governed settings, migrations, tests, docs or workflows. The agent writes nothing to the repository.
3. **A person makes the pull request.** `python scripts/incident_to_pr.py <incident id> --push` applies the stored diff on a new branch and opens a PR. Add a regression test before you
   push. CI runs the backend tests, evals and the web checks. **A person reviews and merges (T4).**
4. **Canary.** Deploy the merged change to a slice of traffic. Feed the error counts for the old and new release to
   `python scripts/canary_watch.py ...`: exit 0 promote, 2 wait, 1 roll back. It rolls back when the error rate more than doubles AND rises by more than one percentage point,
   or when it cannot tell after 30 minutes. Rolling back is your platform's redeploy-previous-image step; this repository does not do it for you.
5. **Close the incident** on the Incidents page (resolved or dismissed).

Not built: the preview environment and the automatic traffic split (they depend on where this is deployed), and an alert to a pager when an incident opens.
