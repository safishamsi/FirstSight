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
            callback(false)
            return
        }

        connectCallback = callback
        val payload = JSONObject().apply {
            put("user_id", VisionAgentConfig.userId)
            put("user_name", VisionAgentConfig.userName)
            put("call_type", "default")
            put("start_agent_session", true)
        }
        val request = Request.Builder()
            .url(sessionsUrl)
            .post(payload.toString().toRequestBody(JSON_MEDIA_TYPE))
            .build()

        client.newCall(request).enqueue(object : okhttp3.Callback {
            override fun onFailure(call: okhttp3.Call, e: IOException) {
                Log.e(TAG, "Session bootstrap failed", e)
                resolveConnect(false)
                onDisconnected?.invoke(e.message)
            }

            override fun onResponse(call: okhttp3.Call, response: Response) {
                response.use {
                    if (!response.isSuccessful) {
                        resolveConnect(false)
                        onDisconnected?.invoke("Bootstrap failed (${response.code})")
                        return
                    }
                    val body = response.body?.string().orEmpty()
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
                    activeSessionId = bootstrap.sessionId
                    onBootstrap?.invoke(bootstrap)
                    openWebSocket(bootstrap.sessionId)
                }
            }
        })
    }

    fun disconnect() {
        webSocket?.close(1000, null)
        webSocket = null
        activeSessionId = null
        resolveConnect(false)
    }

    fun sendAudio(data: ByteArray) {
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
        val json = JSONObject().apply {
            put("realtimeInput", JSONObject().apply {
                put("video", JSONObject().apply {
                    put("mimeType", "image/jpeg")
                    put("data", Base64.encodeToString(baos.toByteArray(), Base64.NO_WRAP))
                })
            })
        }
        webSocket?.send(json.toString())
    }

    fun sendTextMessage(text: String) {
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

    private fun openWebSocket(sessionId: String) {
        val streamUrl = VisionAgentConfig.streamUrl(sessionId)
        if (streamUrl == null) {
            resolveConnect(false)
            return
        }

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
                Log.e(TAG, "Backend websocket failure", t)
                resolveConnect(false)
                onDisconnected?.invoke(t.message)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                resolveConnect(false)
                onDisconnected?.invoke("Connection closed ($code: $reason)")
            }
        })
    }

    private fun handleMessage(text: String) {
        try {
            val json = JSONObject(text)
            when (json.optString("type")) {
                "session_ready" -> {
                    return
                }

                "ack" -> {
                    val videoFrames = json.optInt("video_frames", 0)
                    val audioChunks = json.optInt("audio_chunks", 0)
                    onAck?.invoke(videoFrames, audioChunks)
                    return
                }

                "bridge_error" -> {
                    onDisconnected?.invoke(json.optString("message", "Realtime bridge error"))
                    return
                }
            }

            if (json.has("setupComplete")) {
                resolveConnect(true)
                return
            }

            if (json.has("serverContent")) {
                val serverContent = json.getJSONObject("serverContent")
                if (serverContent.has("inputTranscription")) {
                    val transcriptText =
                        serverContent.getJSONObject("inputTranscription").optString("text", "")
                    if (transcriptText.isNotEmpty()) {
                        onInputTranscription?.invoke(transcriptText)
                    }
                }
                if (serverContent.has("outputTranscription")) {
                    val transcriptText =
                        serverContent.getJSONObject("outputTranscription").optString("text", "")
                    if (transcriptText.isNotEmpty()) {
                        onOutputTranscription?.invoke(transcriptText)
                    }
                }
                if (serverContent.optBoolean("turnComplete", false)) {
                    onTurnComplete?.invoke()
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to parse backend message", e)
        }
    }

    private fun sendSetupMessage() {
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
        val callback = connectCallback
        connectCallback = null
        callback?.invoke(success)
    }
}
