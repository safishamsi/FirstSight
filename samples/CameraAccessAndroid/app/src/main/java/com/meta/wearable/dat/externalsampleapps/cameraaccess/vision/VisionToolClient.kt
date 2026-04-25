package com.meta.wearable.dat.externalsampleapps.cameraaccess.vision

import android.graphics.Bitmap
import android.util.Base64
import android.util.Log
import com.meta.wearable.dat.externalsampleapps.cameraaccess.gemini.GeminiConfig
import java.io.ByteArrayOutputStream
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class VisionToolClient(
    private val client: OkHttpClient =
        OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .callTimeout(75, TimeUnit.SECONDS)
            .build(),
) {
    companion object {
        private const val TAG = "VisionToolClient"
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()
    }

    suspend fun locateObject(
        bitmap: Bitmap,
        query: String,
        includeSegmentation: Boolean,
    ): ObjectDetectionResult =
        withContext(Dispatchers.IO) {
            val startedAt = System.currentTimeMillis()
            val baseUrl = GeminiConfig.visionToolBaseUrl.trim()
            check(baseUrl.isNotEmpty()) {
                "Vision tool URL is not configured. Add it in Settings > Vision Tool."
            }

            Log.d(
                TAG,
                "locateObject start query='$query' includeSegmentation=$includeSegmentation frame=${bitmap.width}x${bitmap.height} url=$baseUrl",
            )

            val payload =
                JSONObject()
                    .put("query", query)
                    .put("includeSegmentation", includeSegmentation)
                    .put("imageBase64", bitmap.toJpegBase64())
                    .put("frameWidth", bitmap.width)
                    .put("frameHeight", bitmap.height)

            val request =
                Request.Builder()
                    .url("${baseUrl.removeSuffix("/")}/locate-object")
                    .post(payload.toString().toRequestBody(JSON_MEDIA_TYPE))
                    .apply {
                        val token = GeminiConfig.visionToolAuthToken.trim()
                        if (token.isNotEmpty()) {
                            header("Authorization", "Bearer $token")
                        }
                    }
                    .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                val elapsed = System.currentTimeMillis() - startedAt
                Log.d(
                    TAG,
                    "locateObject response query='$query' code=${response.code} elapsedMs=$elapsed bodyPreview='${body.take(240)}'",
                )
                check(response.isSuccessful) {
                    "Vision tool failed (${response.code}): ${body.take(300)}"
                }
                check(body.isNotBlank()) { "Vision tool returned an empty response." }
                ObjectDetectionResult.fromJSON(JSONObject(body)).also { result ->
                    Log.d(
                        TAG,
                        "locateObject parsed query='$query' found=${result.found} label='${result.label}' confidence=${result.confidence}",
                    )
                }
            }
        }

    suspend fun guideStep(
        task: String,
        stepIndex: Int,
        observedLabel: String?,
        objectFound: Boolean,
        sessionId: String? = null,
    ): JSONObject =
        withContext(Dispatchers.IO) {
            val startedAt = System.currentTimeMillis()
            val baseUrl = GeminiConfig.visionToolBaseUrl.trim()
            check(baseUrl.isNotEmpty()) {
                "Vision tool URL is not configured. Add it in Settings > Vision Tool."
            }

            Log.d(
                TAG,
                "guideStep start task='$task' stepIndex=$stepIndex observedLabel='${observedLabel ?: ""}' objectFound=$objectFound url=$baseUrl",
            )

            val payload =
                JSONObject()
                    .put("task", task)
                    .put("stepIndex", stepIndex)
                    .put("observedLabel", observedLabel)
                    .put("objectFound", objectFound)
                    .put("sessionId", sessionId)

            val request =
                Request.Builder()
                    .url("${baseUrl.removeSuffix("/")}/guide-step")
                    .post(payload.toString().toRequestBody(JSON_MEDIA_TYPE))
                    .apply {
                        val token = GeminiConfig.visionToolAuthToken.trim()
                        if (token.isNotEmpty()) {
                            header("Authorization", "Bearer $token")
                        }
                    }
                    .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                val elapsed = System.currentTimeMillis() - startedAt
                Log.d(
                    TAG,
                    "guideStep response stepIndex=$stepIndex code=${response.code} elapsedMs=$elapsed bodyPreview='${body.take(240)}'",
                )
                check(response.isSuccessful) {
                    "Guide step failed (${response.code}): ${body.take(300)}"
                }
                check(body.isNotBlank()) { "Guide step returned an empty response." }
                JSONObject(body)
            }
        }

    suspend fun trackTarget(
        bitmap: Bitmap,
        query: String,
        previousBbox: JSONObject?,
    ): ObjectDetectionResult =
        withContext(Dispatchers.IO) {
            val startedAt = System.currentTimeMillis()
            val baseUrl = GeminiConfig.visionToolBaseUrl.trim()
            check(baseUrl.isNotEmpty()) {
                "Vision tool URL is not configured. Add it in Settings > Vision Tool."
            }

            Log.d(
                TAG,
                "trackTarget start query='$query' frame=${bitmap.width}x${bitmap.height} url=$baseUrl",
            )

            val payload =
                JSONObject()
                    .put("query", query)
                    .put("imageBase64", bitmap.toJpegBase64())
                    .put("frameWidth", bitmap.width)
                    .put("frameHeight", bitmap.height)
                    .put("previousBbox", previousBbox)

            val request =
                Request.Builder()
                    .url("${baseUrl.removeSuffix("/")}/track-target")
                    .post(payload.toString().toRequestBody(JSON_MEDIA_TYPE))
                    .apply {
                        val token = GeminiConfig.visionToolAuthToken.trim()
                        if (token.isNotEmpty()) {
                            header("Authorization", "Bearer $token")
                        }
                    }
                    .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                val elapsed = System.currentTimeMillis() - startedAt
                Log.d(
                    TAG,
                    "trackTarget response query='$query' code=${response.code} elapsedMs=$elapsed bodyPreview='${body.take(240)}'",
                )
                check(response.isSuccessful) {
                    "Track target failed (${response.code}): ${body.take(300)}"
                }
                check(body.isNotBlank()) { "Track target returned an empty response." }
                ObjectDetectionResult.fromJSON(JSONObject(body))
            }
        }

    suspend fun startGuidance(
        task: String?,
        sessionId: String? = null,
    ): JSONObject = postJson(
        endpoint = "/start-guidance",
        payload =
            JSONObject()
                .put("task", task)
                .put("sessionId", sessionId),
        logName = "startGuidance",
    )

    suspend fun advanceStep(sessionId: String?): JSONObject = postJson(
        endpoint = "/advance-step",
        payload = JSONObject().put("sessionId", sessionId),
        logName = "advanceStep",
    )

    private suspend fun postJson(
        endpoint: String,
        payload: JSONObject,
        logName: String,
    ): JSONObject =
        withContext(Dispatchers.IO) {
            val startedAt = System.currentTimeMillis()
            val baseUrl = GeminiConfig.visionToolBaseUrl.trim()
            check(baseUrl.isNotEmpty()) {
                "Vision tool URL is not configured. Add it in Settings > Vision Tool."
            }
            Log.d(TAG, "$logName start endpoint=$endpoint payload='${payload.toString().take(240)}'")
            val request =
                Request.Builder()
                    .url("${baseUrl.removeSuffix("/")}$endpoint")
                    .post(payload.toString().toRequestBody(JSON_MEDIA_TYPE))
                    .apply {
                        val token = GeminiConfig.visionToolAuthToken.trim()
                        if (token.isNotEmpty()) {
                            header("Authorization", "Bearer $token")
                        }
                    }
                    .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                val elapsed = System.currentTimeMillis() - startedAt
                Log.d(
                    TAG,
                    "$logName response endpoint=$endpoint code=${response.code} elapsedMs=$elapsed bodyPreview='${body.take(240)}'",
                )
                check(response.isSuccessful) {
                    "$logName failed (${response.code}): ${body.take(300)}"
                }
                check(body.isNotBlank()) { "$logName returned an empty response." }
                JSONObject(body)
            }
        }

    suspend fun inspectObject(
        query: String?,
        image: Bitmap?,
    ): JSONObject =
        withContext(Dispatchers.IO) {
            val payload =
                JSONObject()
                    .put("query", query)
                    .put("imageBase64", image?.toJpegBase64())
            postJson("/inspect-object", payload, "inspectObject")
        }
}

private fun Bitmap.toJpegBase64(): String {
    val output = ByteArrayOutputStream()
    compress(Bitmap.CompressFormat.JPEG, 85, output)
    return Base64.encodeToString(output.toByteArray(), Base64.NO_WRAP)
}
