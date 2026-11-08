# pramaan — Python SDK

```bash
pip install ./packages/sdk/python        # or: pip install pramaan  once published
```

```python
from pramaan import Pramaan

p = Pramaan(base_url="https://your-pramaan-host")      # public endpoints need no key

# Is this certificate genuine?
result = p.verify("PRM-ABCDEFGHJK")
print(result["valid"], result["reason"])

# Ask in plain English, in any language. Every hit says why it matched.
for hit in p.search("clean-energy innovators in Karnataka")["results"]:
    print(hit["full_name"], hit["reasons"])

# Try to forge a certificate: the API names exactly what changed.
check = p.check_payload("PRM-ABCDEFGHJK", {**result["payload"], "full_name": "Someone Else"})
print(check["valid"], check["changed_fields"])        # False ['full_name']
```

Authenticated features use an API key (`pk_live_…`) created at **/developers**:

```python
p = Pramaan(api_key="pk_live_…")
hook = p.create_webhook("https://example.com/hooks/pramaan", ["certificate.issued", "profile.approved"])
secret = hook["secret"]        # shown once — store it
```

### Receiving webhooks

```python
from pramaan import verify_webhook

@app.post("/hooks/pramaan")
async def hook(request: Request):
    body = await request.body()                       # the RAW bytes, not re-serialised JSON
    if not verify_webhook(SECRET, request.headers["X-Pramaan-Signature"], body):
        return Response(status_code=400)
    event = json.loads(body)
    ...
```

### Async

```python
from pramaan import AsyncPramaan
async with AsyncPramaan() as p:
    print((await p.verify("PRM-…"))["valid"])
```

Errors: `PramaanError` (has `.status`, `.detail`) and `RateLimited` (`.retry_after`).
