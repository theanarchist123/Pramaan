"""Try a few plain-English searches against the running API and print what came back."""
import json
import sys
import time
import urllib.request

API = "http://localhost:8000"
queries = sys.argv[1:] or [
    "clean-energy innovators in Karnataka who have collaborated with academic institutions",
    "सौर ऊर्जा वैज्ञानिक",  # "solar energy scientist" in Hindi
    "someone who teaches classical dance to poor children",
    "journalists investigating river pollution",
]
for q in queries:
    req = urllib.request.Request(f"{API}/v1/search", data=json.dumps({"query": q, "limit": 4}).encode(),
                                 headers={"Content-Type": "application/json"})
    t = time.time()
    r = json.load(urllib.request.urlopen(req, timeout=120))
    print(f"\n? {q}\n  plan: state={r['plan']['state']} sector={r['plan']['sector']} -> “{r['plan']['semantic_query'][:70]}” "
          f"| {r['embedder']} | {time.time() - t:.1f}s | relaxed={r['relaxed']}")
    for h in r["results"]:
        print(f"  {h['score']:.2f}  {h['full_name']:32s} {h['sector']:15s} {h['state']:12s} | {'; '.join(h['reasons'])[:90]}")
