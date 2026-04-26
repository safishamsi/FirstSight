package com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent

import android.util.Log
import java.util.concurrent.TimeUnit
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

data class VisionAgentGuideSummary(
    val id: String,
    val title: String,
    val summary: String,
    val incidentType: String?,
    val severity: String,
)

data class VisionAgentGuideDetail(
    val id: String,
    val title: String,
    val summary: String,
    val incidentType: String?,
    val severity: String,
    val manualMarkdown: String,
    val checklistTemplate: List<String>,
)

class VisionAgentGuideClient {
    companion object {
        private const val TAG = "VisionAgentGuideClient"
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()
    }

    private val client =
        OkHttpClient.Builder()
            .callTimeout(10, TimeUnit.SECONDS)
            .build()

    fun listGuides(): List<VisionAgentGuideSummary> {
        val url = VisionAgentConfig.protocolsUrl() ?: return emptyList()
        val request = Request.Builder().url(url).get().build()
        return executeGuideList(request)
    }

    fun searchGuides(query: String): List<VisionAgentGuideSummary> {
        val baseUrl = VisionAgentConfig.protocolSearchUrl()?.toHttpUrlOrNull() ?: return emptyList()
        val url =
            baseUrl.newBuilder()
                .addQueryParameter("q", query.trim())
                .addQueryParameter("limit", "12")
                .build()
        val request = Request.Builder().url(url).get().build()
        return executeGuideList(request)
    }

    fun fetchGuide(protocolId: String): VisionAgentGuideDetail? {
        val url = VisionAgentConfig.protocolDetailUrl(protocolId) ?: return null
        val request = Request.Builder().url(url).get().build()
        return try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    Log.w(TAG, "Guide detail failed code=${response.code} protocolId=$protocolId")
                    return null
                }
                val payload = JSONObject(response.body?.string().orEmpty())
                payload.toGuideDetail()
            }
        } catch (e: Exception) {
            Log.w(TAG, "Guide detail fetch failed protocolId=$protocolId", e)
            null
        }
    }

    fun loadGuideIntoSession(
        sessionId: String,
        protocolId: String,
        matchedQuery: String? = null,
    ): Boolean {
        val url = VisionAgentConfig.checklistSetUrl(sessionId) ?: return false
        val payload =
            JSONObject().apply {
                put("protocol_id", protocolId)
                if (!matchedQuery.isNullOrBlank()) {
                    put("matched_query", matchedQuery)
                }
            }
        val request =
            Request.Builder()
                .url(url)
                .post(payload.toString().toRequestBody(JSON_MEDIA_TYPE))
                .build()
        return try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    Log.w(
                        TAG,
                        "Guide session load failed code=${response.code} sessionId=$sessionId protocolId=$protocolId",
                    )
                    return false
                }
                true
            }
        } catch (e: Exception) {
            Log.w(TAG, "Guide session load failed sessionId=$sessionId protocolId=$protocolId", e)
            false
        }
    }

    fun clearGuideFromSession(sessionId: String): Boolean {
        val url = VisionAgentConfig.checklistClearUrl(sessionId) ?: return false
        val request = Request.Builder().url(url).delete().build()
        return try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    Log.w(TAG, "Guide clear failed code=${response.code} sessionId=$sessionId")
                    return false
                }
                true
            }
        } catch (e: Exception) {
            Log.w(TAG, "Guide clear failed sessionId=$sessionId", e)
            false
        }
    }

    private fun executeGuideList(request: Request): List<VisionAgentGuideSummary> {
        return try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    Log.w(TAG, "Guide list failed code=${response.code}")
                    return emptyList()
                }
                val body = response.body?.string().orEmpty()
                val array = JSONArray(body)
                buildList {
                    for (index in 0 until array.length()) {
                        val item = array.optJSONObject(index) ?: continue
                        add(item.toGuideSummary())
                    }
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "Guide list fetch failed", e)
            emptyList()
        }
    }
}

private fun JSONObject.toGuideSummary(): VisionAgentGuideSummary =
    VisionAgentGuideSummary(
        id = optString("id").ifBlank { optString("protocol_id") },
        title = optString("title"),
        summary = optString("summary"),
        incidentType = optString("incident_type").ifBlank { null },
        severity = optString("severity", "medium"),
    )

private fun JSONObject.toGuideDetail(): VisionAgentGuideDetail =
    VisionAgentGuideDetail(
        id = optString("id"),
        title = optString("title"),
        summary = optString("summary"),
        incidentType = optString("incident_type").ifBlank { null },
        severity = optString("severity", "medium"),
        manualMarkdown = optString("manual_markdown"),
        checklistTemplate =
            buildList {
                val array = optJSONArray("checklist_template") ?: JSONArray()
                for (index in 0 until array.length()) {
                    val item = array.optJSONObject(index) ?: continue
                    val label = item.optString("label")
                    if (label.isNotBlank()) {
                        add(label)
                    }
                }
            },
    )
