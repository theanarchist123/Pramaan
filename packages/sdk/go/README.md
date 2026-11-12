# Pramaan Go SDK

Standard library only. Methods return the server's JSON decoded into `map[string]any`.

```go
c := pramaan.New("https://api.example.org", "")   // public checks need no key
res, err := c.Verify(ctx, "PRM-ABCDEFGHJK")
err = pramaan.VerifyWebhook(secret, header, body, 0)
```

Status: written without a Go toolchain on the author's machine, so it has NOT been compiled or run. `go test ./...` is the first thing to do.
The Python contract test (`backend/tests/test_sdk_contract.py`) does check every path it calls against the API's OpenAPI document.
