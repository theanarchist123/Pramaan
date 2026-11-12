# Pramaan Kotlin/JVM SDK

JDK 11+ (`java.net.http`), no runtime dependency. Methods return the server's JSON as a `String`.

```kotlin
val p = Pramaan("https://api.example.org")           // public checks need no key
println(p.verify("PRM-ABCDEFGHJK"))
Pramaan.verifyWebhook(secret, header, bodyBytes)      // false for anything wrong or stale
```

Status: written without a Kotlin toolchain on the author's machine, so it has NOT been compiled or run. `gradle test` is the first thing to do.
The Python contract test (`backend/tests/test_sdk_contract.py`) does check every path it calls against the API's OpenAPI document.
