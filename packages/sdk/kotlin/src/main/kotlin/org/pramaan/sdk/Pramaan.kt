package org.pramaan.sdk

import java.net.URI
import java.net.URLEncoder
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.time.Duration
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/** The API answered with an error. [detail] is the server's message, [retryAfterSeconds] is set on 429. */
class PramaanException(val status: Int, val detail: String, val retryAfterSeconds: Int? = null) : RuntimeException("pramaan: $status: $detail")

/**
 * A small Kotlin/JVM client for the Pramaan public API (JDK 11+ `java.net.http`, no other dependency). Every method returns the server's JSON as a String, so you
 * choose the JSON library (kotlinx.serialization, Moshi, Jackson) and new fields never break you. Public endpoints need no key.
 */
class Pramaan(baseUrl: String, private val apiKey: String? = null, private val http: HttpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build()) {
    private val base = baseUrl.trimEnd('/')

    private fun enc(s: String) = URLEncoder.encode(s, StandardCharsets.UTF_8).replace("+", "%20")
    private fun code(c: String) = c.trim().uppercase()

    private fun call(method: String, path: String, json: String? = null): String {
        val b = HttpRequest.newBuilder(URI.create(base + path)).timeout(Duration.ofSeconds(30)).header("Accept", "application/json")
        if (apiKey != null) b.header("X-API-Key", apiKey)
        if (json != null) b.header("Content-Type", "application/json").method(method, HttpRequest.BodyPublishers.ofString(json))
        else b.method(method, HttpRequest.BodyPublishers.noBody())
        val r = http.send(b.build(), HttpResponse.BodyHandlers.ofString())
        if (r.statusCode() >= 400) {
            val retry = r.headers().firstValue("Retry-After").map { it.toIntOrNull() }.orElse(null)
            throw PramaanException(r.statusCode(), r.body().take(500), retry)
        }
        return r.body()
    }

    private fun quote(s: String) = "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n") + "\""

    fun verify(certCode: String): String = call("GET", "/v1/verify/" + enc(code(certCode)))
    fun verifyBatch(codes: List<String>): String = call("POST", "/v1/verify/batch", "{\"codes\":[" + codes.joinToString(",") { quote(code(it)) } + "]}")
    fun certificate(certCode: String): String = call("GET", "/v1/certificates/" + enc(code(certCode)))
    fun credential(certCode: String): String = call("GET", "/v1/certificates/" + enc(code(certCode)) + "/vc")
    fun search(query: String, limit: Int = 12): String = call("POST", "/v1/search", "{\"query\":" + quote(query) + ",\"limit\":" + limit + "}")
    fun profile(slug: String): String = call("GET", "/v1/profiles/" + enc(slug))
    fun logCheckpoint(): String = call("GET", "/v1/transparency/checkpoint")
    fun publicKeys(): String = call("GET", "/.well-known/pramaan-keys.json")

    companion object {
        /** Check X-Pramaan-Signature ("t=<unix>,v1=<hex hmac-sha256 of "<t>.<body>">"). Returns false for anything wrong, stale or malformed. */
        fun verifyWebhook(secret: String, header: String, body: ByteArray, toleranceSeconds: Long = 300, nowSeconds: Long = System.currentTimeMillis() / 1000): Boolean {
            val parts = header.split(",").mapNotNull { p -> p.trim().split("=", limit = 2).takeIf { it.size == 2 }?.let { it[0] to it[1] } }.toMap()
            val ts = parts["t"]?.toLongOrNull() ?: return false
            val sig = parts["v1"] ?: return false
            if (kotlin.math.abs(nowSeconds - ts) > toleranceSeconds) return false
            val mac = Mac.getInstance("HmacSHA256")
            mac.init(SecretKeySpec(secret.toByteArray(StandardCharsets.UTF_8), "HmacSHA256"))
            mac.update("$ts.".toByteArray(StandardCharsets.UTF_8))
            val want = mac.doFinal(body).joinToString("") { "%02x".format(it) }
            return MessageDigest.isEqual(want.toByteArray(StandardCharsets.UTF_8), sig.toByteArray(StandardCharsets.UTF_8))
        }
    }
}
