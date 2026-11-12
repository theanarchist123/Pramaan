package org.pramaan.sdk

import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class PramaanTest {
    private fun sig(secret: String, ts: Long, body: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(secret.toByteArray(), "HmacSHA256"))
        mac.update("$ts.".toByteArray())
        return mac.doFinal(body.toByteArray()).joinToString("") { "%02x".format(it) }
    }

    @Test
    fun webhookSignatureAcceptsTheRealThingAndRefusesTheRest() {
        val now = 1_800_000_000L
        val body = "{\"id\":\"x\"}"
        val header = "t=$now,v1=" + sig("s3cret", now, body)
        assertTrue(Pramaan.verifyWebhook("s3cret", header, body.toByteArray(), nowSeconds = now))
        assertFalse(Pramaan.verifyWebhook("other", header, body.toByteArray(), nowSeconds = now))
        assertFalse(Pramaan.verifyWebhook("s3cret", header, "{\"id\":\"y\"}".toByteArray(), nowSeconds = now))
        assertFalse(Pramaan.verifyWebhook("s3cret", header, body.toByteArray(), nowSeconds = now + 3600))
        assertFalse(Pramaan.verifyWebhook("s3cret", "garbage", body.toByteArray(), nowSeconds = now))
    }
}
