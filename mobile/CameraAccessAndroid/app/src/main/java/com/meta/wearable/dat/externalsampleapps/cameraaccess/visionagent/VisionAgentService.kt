package com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent

import android.graphics.Bitmap
import android.util.Base64
import android.util.Log
import com.meta.wearable.dat.externalsampleapps.cameraaccess.gemini.GeminiConfig
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import org.json.JSONObject

data class VisionAgentBootstrapPayload(
    val sessionId: String,
    val provider: String,
    val callId: String?,
    val callType: String?,
    val agentSessionId: String?,
    val streamApiKey: String?,
    val streamUserId: String?,
    val streamUserToken: String?,
    val visionAgentStarted: Boolean,
    val visionAgentError: String?,
    val missingConfiguration: List<String>,
)

data class VisionAgentChecklistItemPayload(
    val id: String,
    val label: String,
    val kind: String,
    val status: String,
    val sourceProtocolId: String?,
)

data class VisionAgentSpatialPointPayload(
    val x: Float,
    val y: Float,
)

data class VisionAgentSpatialBoxPayload(
    val xmin: Float,
    val ymin: Float,
    val xmax: Float,
    val ymax: Float,
)

data class VisionAgentSpatialOverlayPayload(
    val id: String,
    val kind: String,
    val label: String?,
    val text: String?,
    val color: String?,
    val source: String?,
    val emphasis: String?,
    val point: VisionAgentSpatialPointPayload?,
    val box: VisionAgentSpatialBoxPayload?,
    val points: List<VisionAgentSpatialPointPayload>,
)

data class VisionAgentSessionStatusPayload(
    val activeProtocolId: String?,
    val activeProtocolTitle: String?,
    val activeProtocolSummary: String?,
    val activeProtocolManual: String?,
    val lastAgentPromptedStep: String?,
    val spatialContextSummary: String?,
    val spatialOverlays: List<VisionAgentSpatialOverlayPayload>,
    val riskFlags: List<String>,
    val activeChecklist: List<VisionAgentChecklistItemPayload>,
)

data class VisionAgentSpatialOverlayUpsertPayload(
    val contextSummary: String?,
    val mode: String?,
    val ttlMs: Int?,
    val replace: Boolean,
    val overlays: List<JSONObject>,
)

class VisionAgentService {
    companion object {
        private const val TAG = "VisionAgentService"
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()
    }

    var onBootstrap: ((VisionAgentBootstrapPayload) -> Unit)? = null
    var onAck: ((Int, Int) -> Unit)? = null
    var onDisconnected: ((String?) -> Unit)? = null
    var onInputTranscription: ((String) -> Unit)? = null
    var onOutputTranscription: ((String) -> Unit)? = null
    var onAudioReceived: ((ByteArray) -> Unit)? = null
    var onTurnComplete: (() -> Unit)? = null

    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(10, TimeUnit.SECONDS)
        .build()

    private var webSocket: WebSocket? = null
    private var connectCallback: ((Boolean) -> Unit)? = null
    private var activeSessionId: String? = null

    fun connect(callback: (Boolean) -> Unit) {
        val sessionsUrl = VisionAgentConfig.sessionsUrl()
        if (sessionsUrl == null) {
            Log.e(TAG, "Vision Agent backend sessions URL is not configured")
            callback(false)
            return
        }

        connectCallback = callback
        val payload = JSONObject().apply {
            put("user_id", VisionAgentConfig.userId)
            put("user_name", VisionAgentConfig.userName)
            put("call_type", "default")
            put("start_agent_session", true)
            put("runtime_config", JSONObject().apply {
                put("speech_pipeline", VisionAgentConfig.runtimeConfig.speechPipeline)
                put("enable_pose_processor", VisionAgentConfig.runtimeConfig.enablePoseProcessor)
                put("gemini_llm_model", VisionAgentConfig.runtimeConfig.geminiLlmModel)
                put("fast_whisper_model_size", VisionAgentConfig.runtimeConfig.fastWhisperModelSize)
                put("fast_whisper_device", VisionAgentConfig.runtimeConfig.fastWhisperDevice)
                put("pipeline_turn_delay_ms", VisionAgentConfig.runtimeConfig.pipelineTurnDelayMs)
                put("backend_tts_enabled", VisionAgentConfig.runtimeConfig.backendTtsEnabled)
            })
        }
        val request = Request.Builder()
            .url(sessionsUrl)
            .post(payload.toString().toRequestBody(JSON_MEDIA_TYPE))
            .build()
        Log.d(
            TAG,
            "Bootstrapping Vision Agent session url=$sessionsUrl userId=${VisionAgentConfig.userId} userName=${VisionAgentConfig.userName}",
        )

        client.newCall(request).enqueue(object : okhttp3.Callback {
            override fun onFailure(call: okhttp3.Call, e: IOException) {
                Log.e(TAG, "Session bootstrap failed", e)
                onDisconnected?.invoke(e.message)
                resolveConnect(false)
            }

            override fun onResponse(call: okhttp3.Call, response: Response) {
                response.use {
                    if (!response.isSuccessful) {
                        onDisconnected?.invoke("Bootstrap failed (${response.code})")
                        resolveConnect(false)
                        return
                    }
                    val body = response.body?.string().orEmpty()
                    Log.d(TAG, "Bootstrap response code=${response.code} body=$body")
                    val json = JSONObject(body)
                    val bootstrap = VisionAgentBootstrapPayload(
                        sessionId = json.getString("session_id"),
                        provider = json.optString("provider", "unknown"),
                        callId = json.optString("call_id").ifBlank { null },
                        callType = json.optString("call_type").ifBlank { null },
                        agentSessionId = json.optString("agent_session_id").ifBlank { null },
                        streamApiKey = json.optString("stream_api_key").ifBlank { null },
                        streamUserId = json.optString("stream_user_id").ifBlank { null },
                        streamUserToken = json.optString("stream_user_token").ifBlank { null },
                        visionAgentStarted = json.optBoolean("vision_agent_started", false),
                        visionAgentError = json.optString("vision_agent_error").ifBlank { null },
                        missingConfiguration = buildList {
                            val array = json.optJSONArray("missing_configuration") ?: return@buildList
                            for (index in 0 until array.length()) {
                                add(array.optString(index))
                            }
                        },
                    )
                    Log.d(
                        TAG,
                        "Bootstrap parsed sessionId=${bootstrap.sessionId} provider=${bootstrap.provider} visionAgentStarted=${bootstrap.visionAgentStarted} missing=${bootstrap.missingConfiguration}",
                    )
                    activeSessionId = bootstrap.sessionId
                    onBootstrap?.invoke(bootstrap)
                    openWebSocket(bootstrap.sessionId)
                }
            }
        })
    }

    fun disconnect() {
        Log.d(TAG, "Disconnecting Vision Agent session sessionId=$activeSessionId")
        webSocket?.close(1000, null)
        webSocket = null
        activeSessionId = null
        resolveConnect(false)
    }

    fun sendAudio(data: ByteArray) {
        Log.v(TAG, "Sending audio chunk bytes=${data.size} sessionId=$activeSessionId")
        val json = JSONObject().apply {
            put("realtimeInput", JSONObject().apply {
                put("audio", JSONObject().apply {
                    put("mimeType", "audio/pcm;rate=16000")
                    put("data", Base64.encodeToString(data, Base64.NO_WRAP))
                })
            })
        }
        webSocket?.send(json.toString())
    }

    fun sendVideoFrame(bitmap: Bitmap) {
        val baos = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, GeminiConfig.VIDEO_JPEG_QUALITY, baos)
        val imageBytes = baos.toByteArray()
        Log.v(TAG, "Sending video frame bytes=${imageBytes.size} sessionId=$activeSessionId")
        val json = JSONObject().apply {
            put("realtimeInput", JSONObject().apply {
                put("video", JSONObject().apply {
                    put("mimeType", "image/jpeg")
                    put("data", Base64.encodeToString(imageBytes, Base64.NO_WRAP))
                })
            })
        }
        webSocket?.send(json.toString())
    }

    fun sendTextMessage(text: String) {
        Log.d(TAG, "Sending text message sessionId=$activeSessionId text=$text")
        val json = JSONObject().apply {
            put("clientContent", JSONObject().apply {
                put("turns", JSONArray().put(JSONObject().apply {
                    put("role", "user")
                    put("parts", JSONArray().put(JSONObject().apply {
                        put("text", text)
                    }))
                }))
            })
        }
        webSocket?.send(json.toString())
    }

    fun fetchSessionStatus(sessionId: String): VisionAgentSessionStatusPayload? {
        val statusUrl = VisionAgentConfig.sessionStatusUrl(sessionId) ?: return null
        val request = Request.Builder().url(statusUrl).get().build()
        return try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    Log.w(TAG, "Session status failed code=${response.code} sessionId=$sessionId")
                    return null
                }
                val body = response.body?.string().orEmpty()
                val json = JSONObject(body)
                val incidentState = json.optJSONObject("incident_state") ?: JSONObject()
                val checklistItems = buildList {
                    val array = json.optJSONArray("active_checklist") ?: JSONArray()
                    for (index in 0 until array.length()) {
                        val item = array.optJSONObject(index) ?: continue
                        add(
                            VisionAgentChecklistItemPayload(
                                id = item.optString("id"),
                                label = item.optString("label"),
                                kind = item.optString("kind", "action"),
                                status = item.optString("status", "pending"),
                                sourceProtocolId = item.optString("source_protocol_id").ifBlank { null },
                            ),
                        )
                    }
                }
                VisionAgentSessionStatusPayload(
                    activeProtocolId = incidentState.optString("active_protocol_id").ifBlank { null },
                    activeProtocolTitle = incidentState.optString("active_protocol_title").ifBlank { null },
                    activeProtocolSummary = incidentState.optString("active_protocol_summary").ifBlank { null },
                    activeProtocolManual = incidentState.optString("active_protocol_manual").ifBlank { null },
                    lastAgentPromptedStep = incidentState.optString("last_agent_prompted_step").ifBlank { null },
                    spatialContextSummary = json.optString("spatial_context_summary").ifBlank { null },
                    spatialOverlays =
                        buildList {
                            val array = json.optJSONArray("spatial_overlays") ?: JSONArray()
                            for (index in 0 until array.length()) {
                                val item = array.optJSONObject(index) ?: continue
                                add(item.toSpatialOverlayPayload() ?: continue)
                            }
                        },
                    riskFlags = buildList {
                        val array = incidentState.optJSONArray("risk_flags") ?: JSONArray()
                        for (index in 0 until array.length()) {
                            add(array.optString(index))
                        }
                    },
                    activeChecklist = checklistItems,
                )
            }
        } catch (e: Exception) {
            Log.w(TAG, "Session status fetch failed sessionId=$sessionId", e)
            null
        }
    }

    fun setSpatialOverlays(
        sessionId: String,
        payload: VisionAgentSpatialOverlayUpsertPayload,
    ): Boolean {
        val url = VisionAgentConfig.spatialOverlaysUrl(sessionId) ?: return false
        val requestPayload =
            JSONObject().apply {
                put("replace", payload.replace)
                put("context_summary", payload.contextSummary)
                put("mode", payload.mode)
                put("ttl_ms", payload.ttlMs)
                put(
                    "overlays",
                    JSONArray().apply {
                        payload.overlays.forEach { put(it) }
                    },
                )
            }
        val request =
            Request.Builder()
                .url(url)
                .post(requestPayload.toString().toRequestBody(JSON_MEDIA_TYPE))
                .build()
        return try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    Log.w(TAG, "Spatial overlays set failed code=${response.code} sessionId=$sessionId")
                    return false
                }
                true
            }
        } catch (e: Exception) {
            Log.w(TAG, "Spatial overlays set failed sessionId=$sessionId", e)
            false
        }
    }

    fun clearSpatialOverlays(sessionId: String): Boolean {
        val url = VisionAgentConfig.spatialOverlaysUrl(sessionId) ?: return false
        val request = Request.Builder().url(url).delete().build()
        return try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    Log.w(TAG, "Spatial overlays clear failed code=${response.code} sessionId=$sessionId")
                    return false
                }
                true
            }
        } catch (e: Exception) {
            Log.w(TAG, "Spatial overlays clear failed sessionId=$sessionId", e)
            false
        }
    }

    private fun openWebSocket(sessionId: String) {
        val streamUrl = VisionAgentConfig.streamUrl(sessionId)
        if (streamUrl == null) {
            Log.e(TAG, "Vision Agent backend stream URL is null for sessionId=$sessionId")
            resolveConnect(false)
            return
        }

        Log.d(TAG, "Opening backend websocket url=$streamUrl sessionId=$sessionId")
        val request = Request.Builder().url(streamUrl).build()
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "Backend websocket opened for session=$sessionId")
                sendSetupMessage()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                handleMessage(text)
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                handleMessage(bytes.utf8())
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "Backend websocket failure code=${response?.code}", t)
                onDisconnected?.invoke(t.message)
                resolveConnect(false)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.w(TAG, "Backend websocket closing session=$sessionId code=$code reason=$reason")
                onDisconnected?.invoke("Connection closed ($code: $reason)")
                resolveConnect(false)
            }
        })
    }

    private fun handleMessage(text: String) {
        try {
            Log.v(TAG, "Backend message: $text")
            val json = JSONObject(text)
            when (json.optString("type")) {
                "session_ready" -> {
                    Log.d(
                        TAG,
                        "session_ready sessionId=${json.optString("session_id")} provider=${json.optString("provider")} bridgeActive=${json.optBoolean("bridge_active")} bridgeError=${json.optString("bridge_error")}",
                    )
                    return
                }

                "ack" -> {
                    val videoFrames = json.optInt("video_frames", 0)
                    val audioChunks = json.optInt("audio_chunks", 0)
                    Log.d(TAG, "ack videoFrames=$videoFrames audioChunks=$audioChunks")
                    onAck?.invoke(videoFrames, audioChunks)
                    return
                }

                "bridge_error" -> {
                    Log.e(TAG, "bridge_error ${json.optString("message", "Realtime bridge error")}")
                    onDisconnected?.invoke(json.optString("message", "Realtime bridge error"))
                    return
                }
            }

            if (json.has("setupComplete")) {
                Log.d(TAG, "setupComplete received sessionId=$activeSessionId")
                resolveConnect(true)
                return
            }

            if (json.has("serverContent")) {
                val serverContent = json.getJSONObject("serverContent")
                if (serverContent.has("inputTranscription")) {
                    val transcriptText =
                        serverContent.getJSONObject("inputTranscription").optString("text", "")
                    if (transcriptText.isNotEmpty()) {
                        Log.d(TAG, "inputTranscription text=$transcriptText")
                        onInputTranscription?.invoke(transcriptText)
                    }
                }
                if (serverContent.has("outputTranscription")) {
                    val transcriptText =
                        serverContent.getJSONObject("outputTranscription").optString("text", "")
                    if (transcriptText.isNotEmpty()) {
                        Log.d(TAG, "outputTranscription text=$transcriptText")
                        onOutputTranscription?.invoke(transcriptText)
                    }
                }
                if (serverContent.optBoolean("turnComplete", false)) {
                    Log.d(TAG, "turnComplete sessionId=$activeSessionId")
                    onTurnComplete?.invoke()
                }
            }

            if (json.has("audioOutput")) {
                val audioOutput = json.getJSONObject("audioOutput")
                val data = audioOutput.optString("data", "")
                if (data.isNotEmpty()) {
                    val decoded = Base64.decode(data, Base64.DEFAULT)
                    Log.d(TAG, "audioOutput bytes=${decoded.size}")
                    onAudioReceived?.invoke(decoded)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to parse backend message", e)
        }
    }

    private fun sendSetupMessage() {
        Log.d(TAG, "Sending setup message sessionId=$activeSessionId")
        val json = JSONObject().apply {
            put("setup", JSONObject().apply {
                put("model", "backend-adapter")
                put("generationConfig", JSONObject().apply {
                    put("responseModalities", JSONArray().put("AUDIO"))
                })
            })
        }
        webSocket?.send(json.toString())
    }

    private fun resolveConnect(success: Boolean) {
        Log.d(TAG, "resolveConnect success=$success sessionId=$activeSessionId")
        val callback = connectCallback
        connectCallback = null
        callback?.invoke(success)
    }
}

private fun JSONObject.toSpatialPointPayload(): VisionAgentSpatialPointPayload? {
    val x = optDouble("x", Double.NaN).toFloat()
    val y = optDouble("y", Double.NaN).toFloat()
    if (!x.isFinite() || !y.isFinite()) return null
    return VisionAgentSpatialPointPayload(x = x, y = y)
}

private fun JSONObject.toSpatialBoxPayload(): VisionAgentSpatialBoxPayload? {
    val xmin = optDouble("xmin", Double.NaN).toFloat()
    val ymin = optDouble("ymin", Double.NaN).toFloat()
    val xmax = optDouble("xmax", Double.NaN).toFloat()
    val ymax = optDouble("ymax", Double.NaN).toFloat()
    if (!xmin.isFinite() || !ymin.isFinite() || !xmax.isFinite() || !ymax.isFinite()) return null
    return VisionAgentSpatialBoxPayload(
        xmin = xmin,
        ymin = ymin,
        xmax = xmax,
        ymax = ymax,
    )
}

private fun JSONObject.toSpatialOverlayPayload(): VisionAgentSpatialOverlayPayload? {
    val id = optString("id")
    val kind = optString("kind")
    if (id.isBlank() || kind.isBlank()) return null
    return VisionAgentSpatialOverlayPayload(
        id = id,
        kind = kind,
        label = optString("label").ifBlank { null },
        text = optString("text").ifBlank { null },
        color = optString("color").ifBlank { null },
        source = optString("source").ifBlank { null },
        emphasis = optString("emphasis").ifBlank { null },
        point = optJSONObject("point")?.toSpatialPointPayload(),
        box = optJSONObject("box")?.toSpatialBoxPayload(),
        points =
            buildList {
                val array = optJSONArray("points") ?: JSONArray()
                for (index in 0 until array.length()) {
                    val item = array.optJSONObject(index) ?: continue
                    add(item.toSpatialPointPayload() ?: continue)
                }
            },
    )
}
