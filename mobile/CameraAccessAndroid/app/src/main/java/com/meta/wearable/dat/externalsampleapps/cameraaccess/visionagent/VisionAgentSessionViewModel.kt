package com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent

import android.graphics.Bitmap
import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.meta.wearable.dat.externalsampleapps.cameraaccess.gemini.AudioManager
import com.meta.wearable.dat.externalsampleapps.cameraaccess.gemini.GeminiConfig
import com.meta.wearable.dat.externalsampleapps.cameraaccess.stream.StreamingMode
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

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

data class VisionAgentChecklistItem(
    val id: String,
    val label: String,
    val status: String,
)

data class VisionAgentSpatialPoint(
    val x: Float,
    val y: Float,
)

data class VisionAgentSpatialBox(
    val xmin: Float,
    val ymin: Float,
    val xmax: Float,
    val ymax: Float,
)

data class VisionAgentSpatialOverlay(
    val id: String,
    val kind: String,
    val label: String?,
    val text: String?,
    val colorHex: String?,
    val source: String?,
    val emphasis: String?,
    val point: VisionAgentSpatialPoint?,
    val box: VisionAgentSpatialBox?,
    val points: List<VisionAgentSpatialPoint>,
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
    val activeProtocolTitle: String? = null,
    val activeProtocolSummary: String? = null,
    val activeProtocolManual: String? = null,
    val currentChecklistStep: String? = null,
    val checklistItems: List<VisionAgentChecklistItem> = emptyList(),
    val spatialContextSummary: String? = null,
    val spatialOverlays: List<VisionAgentSpatialOverlay> = emptyList(),
    val riskFlags: List<String> = emptyList(),
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
    private var sessionStatusJob: Job? = null

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
            startSessionStatusPolling(bootstrap.sessionId)
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
            refreshSessionStatus()
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
        sessionStatusJob?.cancel()
        sessionStatusJob = null
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

    fun refreshStatus() {
        refreshSessionStatus()
    }

    fun loadGuideIntoSession(
        protocolId: String,
        matchedQuery: String? = null,
        onComplete: (Boolean, String?) -> Unit = { _, _ -> },
    ) {
        val sessionId = _uiState.value.sessionId
        if (sessionId.isNullOrBlank()) {
            onComplete(false, "Start Vision Agent first to attach a guide to the active session.")
            return
        }
        val guideClient = VisionAgentGuideClient()
        viewModelScope.launch {
            val success =
                withContext(Dispatchers.IO) {
                    guideClient.loadGuideIntoSession(
                        sessionId = sessionId,
                        protocolId = protocolId,
                        matchedQuery = matchedQuery,
                    )
                }
            if (success) {
                refreshSessionStatus()
                onComplete(true, null)
            } else {
                onComplete(false, "Failed to load guide into the active session.")
            }
        }
    }

    private fun startSessionStatusPolling(sessionId: String) {
        sessionStatusJob?.cancel()
        sessionStatusJob =
            viewModelScope.launch {
                while (isActive && _uiState.value.isVisionAgentActive && _uiState.value.sessionId == sessionId) {
                    refreshSessionStatus()
                    delay(1500)
                }
            }
    }

    private fun refreshSessionStatus() {
        val sessionId = _uiState.value.sessionId ?: return
        viewModelScope.launch {
            val status =
                withContext(Dispatchers.IO) {
                    visionAgentService.fetchSessionStatus(sessionId)
                } ?: return@launch
            _uiState.value =
                _uiState.value.copy(
                    activeProtocolTitle = status.activeProtocolTitle,
                    activeProtocolSummary = status.activeProtocolSummary,
                    activeProtocolManual = status.activeProtocolManual,
                    currentChecklistStep = status.lastAgentPromptedStep,
                    spatialContextSummary = status.spatialContextSummary,
                    spatialOverlays =
                        status.spatialOverlays.map { overlay ->
                            VisionAgentSpatialOverlay(
                                id = overlay.id,
                                kind = overlay.kind,
                                label = overlay.label,
                                text = overlay.text,
                                colorHex = overlay.color,
                                source = overlay.source,
                                emphasis = overlay.emphasis,
                                point =
                                    overlay.point?.let {
                                        VisionAgentSpatialPoint(x = it.x, y = it.y)
                                    },
                                box =
                                    overlay.box?.let {
                                        VisionAgentSpatialBox(
                                            xmin = it.xmin,
                                            ymin = it.ymin,
                                            xmax = it.xmax,
                                            ymax = it.ymax,
                                        )
                                    },
                                points =
                                    overlay.points.map {
                                        VisionAgentSpatialPoint(x = it.x, y = it.y)
                                    },
                            )
                        },
                    checklistItems =
                        status.activeChecklist.map {
                            VisionAgentChecklistItem(
                                id = it.id,
                                label = it.label,
                                status = it.status,
                            )
                        },
                    riskFlags = status.riskFlags,
                )
        }
    }

    override fun onCleared() {
        super.onCleared()
        sessionStatusJob?.cancel()
        speechPlayer.shutdown()
    }
}
