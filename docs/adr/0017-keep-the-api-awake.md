# ADR 0017: Keep the API awake with a scheduled ping

Status: **accepted 2026-11-19 (owner left the choice to the agent; the free option was picked). Re-decide if the 750-hour allowance is at risk.**

## Problem
The API runs on Render's free plan. A free web service sleeps after a quiet spell, and the next visitor waits roughly 20 to 50 seconds. The live review measured about
19 s on a first visit, which is fatal for a demo.

## Decision
`.github/workflows/keep-warm.yml` calls `GET /healthz` every 10 minutes (and the website's connection banner waits 4 s and then says "Waking up the server" instead of
looking broken, DR-05). It needs one repository variable: `API_URL`.

## Limits (be honest about them)
- GitHub's scheduler can run late or skip a run, so short sleeps can still happen. It narrows the problem; it does not remove it.
- **Checked 2026-11-19** against Render's own pages ([free-tier article](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026), [docs](https://render.com/docs/your-first-deploy)):
  a free web service spins down after **15 minutes** without inbound traffic and takes about a minute to restart; each workspace gets **750 free instance hours per
  calendar month**, shared by all its free services, and when they run out the free services are suspended until next month. Paid instances do not spin down
  (Render markets "always on from $7/month"; confirm the current price on https://render.com/pricing).
- **The ping keeps one service on all month:** 24 h x 31 days = 744 h, which fits inside 750 h only if it is the workspace's only free service. A second free service
  would run the allowance out around the 28th and suspend the API, which is worse than sleeping. Check Billing in the Render dashboard after the first few days.
- Before a demo that matters, open the site once yourself a minute early.

## When to replace it
Move the API to a paid always-on instance (the owner's call) before announcing the product publicly. Then delete the workflow.
