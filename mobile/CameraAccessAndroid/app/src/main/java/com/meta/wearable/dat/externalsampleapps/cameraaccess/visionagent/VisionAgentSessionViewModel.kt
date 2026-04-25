package com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent

import android.graphics.Bitmap
import android.app.Application
import androidx.lifecycle.AndroidViewModel
import com.meta.wearable.dat.externalsampleapps.cameraaccess.gemini.AudioManager
import com.meta.wearable.dat.externalsampleapps.cameraaccess.gemini.GeminiConfig
import com.meta.wearable.dat.externalsampleapps.cameraaccess.stream.StreamingMode
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

sealed class VisionAgentConnectionState {
    object Disconnected : VisionAgentConnectionState()
    object Bootstrapping : VisionAgentConnectionState()
    object Connecting : VisionAgentConnectionState()
    object Ready : VisionAgentConnectionState()
    data class Error(val message: String) : VisionAgentConnectionState()
}

data class VisionAgentTranscriptTurn(
    val userText: String,
    val assistantText: String,
)

data class VisionAgentUiState(
    val isVisionAgentActive: Boolean = false,
    val connectionState: VisionAgentConnectionState = VisionAgentConnectionState.Disconnected,
    val errorMessage: String? = null,
    val sessionId: String? = null,
    val callId: String? = null,
    val agentSessionId: String? = null,
    val provider: String? = null,
    val videoFrames: Int = 0,
    val audioChunks: Int = 0,
    val visionAgentStarted: Boolean = false,
    val visionAgentError: String? = null,
    val userTranscript: String = "",
    val assistantTranscript: String = "",
    val transcriptHistory: List<VisionAgentTranscriptTurn> = emptyList(),
)

class VisionAgentSessionViewModel(application: Application) : AndroidViewModel(application) {
    private val _uiState = MutableStateFlow(VisionAgentUiState())
    val uiState: StateFlow<VisionAgentUiState> = _uiState.asStateFlow()

    private val visionAgentService = VisionAgentService()
    private val audioManager = AudioManager()
    private val speechPlayer = VisionAgentSpeechPlayer(application)
    private var lastVideoFrameTime: Long = 0
    private var backendAudioActive = false
    private var isStoppingSession = false

    var streamingMode: StreamingMode = StreamingMode.GLASSES

    fun startSession() {
        if (_uiState.value.isVisionAgentActive) return
        if (!VisionAgentConfig.isConfigured) {
            _uiState.value = _uiState.value.copy(
                errorMessage = "Vision Agent backend URL not configured. Open Settings and add your backend base URL."
            )
            return
        }

        _uiState.value = _uiState.value.copy(
            isVisionAgentActive = true,
            connectionState = VisionAgentConnectionState.Bootstrapping,
            errorMessage = null,
        )

        audioManager.onAudioCaptured = lambda@{ data ->
            if (streamingMode == StreamingMode.PHONE) {
                visionAgentService.sendAudio(data)
                return@lambda
            }
            visionAgentService.sendAudio(data)
        }

        visionAgentService.onBootstrap = { bootstrap ->
            backendAudioActive = false
            _uiState.value = _uiState.value.copy(
                sessionId = bootstrap.sessionId,
                callId = bootstrap.callId,
                agentSessionId = bootstrap.agentSessionId,
                provider = bootstrap.provider,
                visionAgentStarted = bootstrap.visionAgentStarted,
                visionAgentError = bootstrap.visionAgentError,
                connectionState = VisionAgentConnectionState.Connecting,
            )
        }
        visionAgentService.onAck = { videoFrames, audioChunks ->
            _uiState.value = _uiState.value.copy(
                connectionState = VisionAgentConnectionState.Ready,
                videoFrames = videoFrames,
                audioChunks = audioChunks,
            )
        }
        visionAgentService.onInputTranscription = { text ->
            _uiState.value = _uiState.value.copy(
                userTranscript = _uiState.value.userTranscript + text,
                assistantTranscript = "",
            )
        }
        visionAgentService.onOutputTranscription = { text ->
            _uiState.value = _uiState.value.copy(
                assistantTranscript = _uiState.value.assistantTranscript + text,
            )
        }
        visionAgentService.onAudioReceived = { data ->
            backendAudioActive = true
            audioManager.playAudio(data)
        }
        visionAgentService.onTurnComplete = {
            val current = _uiState.value
            val userText = current.userTranscript.trim()
            val assistantText = current.assistantTranscript.trim()
            if (userText.isNotEmpty() || assistantText.isNotEmpty()) {
                val updatedHistory =
                    (current.transcriptHistory + VisionAgentTranscriptTurn(userText, assistantText))
                        .takeLast(6)
                if (assistantText.isNotEmpty() && !backendAudioActive) {
                    speechPlayer.speak(assistantText)
                }
                _uiState.value = current.copy(
                    userTranscript = "",
                    assistantTranscript = "",
                    transcriptHistory = updatedHistory,
                )
            }
        }
        visionAgentService.onDisconnected = { reason ->
            if (_uiState.value.isVisionAgentActive && !isStoppingSession) {
                val current = _uiState.value
                shutdownSessionTransport(resetUi = false)
                _uiState.value = current.copy(
                    isVisionAgentActive = false,
                    errorMessage = "Vision Agent backend connection lost: ${reason ?: "Unknown error"}",
                    connectionState = VisionAgentConnectionState.Error(reason ?: "Unknown error"),
                )
            }
        }

        visionAgentService.connect { setupOk ->
            if (!setupOk) {
                val baseUrl = VisionAgentConfig.baseUrl
                _uiState.value = _uiState.value.copy(
                    isVisionAgentActive = false,
                    connectionState = VisionAgentConnectionState.Error("Failed to connect to Vision Agent backend at $baseUrl"),
                    errorMessage = "Failed to connect to Vision Agent backend at $baseUrl",
                )
                return@connect
            }
            try {
                audioManager.startCapture()
            } catch (e: Exception) {
                shutdownSessionTransport(resetUi = true)
                _uiState.value = _uiState.value.copy(
                    errorMessage = "Mic capture failed: ${e.message}",
                    connectionState = VisionAgentConnectionState.Error("Mic capture failed"),
                )
            }
        }
    }

    fun stopSession() {
        shutdownSessionTransport(resetUi = true)
    }

    private fun shutdownSessionTransport(resetUi: Boolean) {
        isStoppingSession = true
        audioManager.stopCapture()
        speechPlayer.stop()
        visionAgentService.disconnect()
        lastVideoFrameTime = 0
        backendAudioActive = false
        if (resetUi) {
            _uiState.value = VisionAgentUiState()
        }
        isStoppingSession = false
    }

    fun sendVideoFrameIfThrottled(bitmap: Bitmap) {
        if (!_uiState.value.isVisionAgentActive) return
        val now = System.currentTimeMillis()
        if (now - lastVideoFrameTime < GeminiConfig.VIDEO_FRAME_INTERVAL_MS) return
        lastVideoFrameTime = now
        visionAgentService.sendVideoFrame(bitmap)
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }

    override fun onCleared() {
        super.onCleared()
        speechPlayer.shutdown()
    }
}
