package com.meta.wearable.dat.externalsampleapps.cameraaccess.gemini

import android.graphics.Bitmap
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.meta.wearable.dat.externalsampleapps.cameraaccess.guidance.GuidanceSessionState
import com.meta.wearable.dat.externalsampleapps.cameraaccess.openclaw.OpenClawBridge
import com.meta.wearable.dat.externalsampleapps.cameraaccess.openclaw.OpenClawEventClient
import com.meta.wearable.dat.externalsampleapps.cameraaccess.platform.FocusState
import com.meta.wearable.dat.externalsampleapps.cameraaccess.platform.FocusMarkerParser
import com.meta.wearable.dat.externalsampleapps.cameraaccess.platform.ObjectMentionResolver
import com.meta.wearable.dat.externalsampleapps.cameraaccess.platform.ObjectInfoPanelState
import com.meta.wearable.dat.externalsampleapps.cameraaccess.settings.SettingsManager
import com.meta.wearable.dat.externalsampleapps.cameraaccess.openclaw.OpenClawConnectionState
import com.meta.wearable.dat.externalsampleapps.cameraaccess.openclaw.ToolCallRouter
import com.meta.wearable.dat.externalsampleapps.cameraaccess.openclaw.ToolCallStatus
import com.meta.wearable.dat.externalsampleapps.cameraaccess.stream.StreamingMode
import com.meta.wearable.dat.externalsampleapps.cameraaccess.vision.DetectionOverlay
import com.meta.wearable.dat.externalsampleapps.cameraaccess.vision.VisionToolClient
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

data class GeminiUiState(
    val isGeminiActive: Boolean = false,
    val connectionState: GeminiConnectionState = GeminiConnectionState.Disconnected,
    val isModelSpeaking: Boolean = false,
    val errorMessage: String? = null,
    val userTranscript: String = "",
    val aiTranscript: String = "",
    val toolCallStatus: ToolCallStatus = ToolCallStatus.Idle,
    val openClawConnectionState: OpenClawConnectionState = OpenClawConnectionState.NotConfigured,
    val detectionOverlay: DetectionOverlay? = null,
    val guidanceSession: GuidanceSessionState = GuidanceSessionState(),
    val focusState: FocusState = FocusState(),
    val objectInfoPanel: ObjectInfoPanelState = ObjectInfoPanelState(),
)

class GeminiSessionViewModel : ViewModel() {
    companion object {
        private const val TAG = "GeminiSessionVM"
    }

    private val _uiState = MutableStateFlow(GeminiUiState())
    val uiState: StateFlow<GeminiUiState> = _uiState.asStateFlow()

    private val geminiService = GeminiLiveService()
    private val openClawBridge = OpenClawBridge()
    private val visionToolClient = VisionToolClient()
    private var toolCallRouter: ToolCallRouter? = null
    private val audioManager = AudioManager()
    private val eventClient = OpenClawEventClient()
    private var lastVideoFrameTime: Long = 0
    private var stateObservationJob: Job? = null
    private var trackingJob: Job? = null
    private var overlayMaintenanceJob: Job? = null
    private var lastMarkerFocusAtMs: Long = 0L
    @Volatile private var latestVideoFrame: Bitmap? = null

    var streamingMode: StreamingMode = StreamingMode.GLASSES

    fun startSession() {
        if (_uiState.value.isGeminiActive) return

        if (!GeminiConfig.isConfigured) {
            _uiState.value = _uiState.value.copy(
                errorMessage = "Gemini API key not configured. Open Settings and add your key from https://aistudio.google.com/apikey"
            )
            return
        }

        _uiState.value = _uiState.value.copy(isGeminiActive = true)

        // Wire audio callbacks
        audioManager.onAudioCaptured = lambda@{ data ->
            // Phone mode: mute mic while model speaks to prevent echo
            if (streamingMode == StreamingMode.PHONE && geminiService.isModelSpeaking.value) return@lambda
            geminiService.sendAudio(data)
        }

        geminiService.onAudioReceived = { data ->
            audioManager.playAudio(data)
        }

        geminiService.onInterrupted = {
            audioManager.stopPlayback()
        }

        geminiService.onTurnComplete = {
            _uiState.value = _uiState.value.copy(userTranscript = "")
        }

        geminiService.onInputTranscription = { text ->
            _uiState.value = _uiState.value.copy(
                userTranscript = _uiState.value.userTranscript + text,
                aiTranscript = ""
            )
        }

        geminiService.onOutputTranscription = { text ->
            val parsed = FocusMarkerParser.parse(text)
            _uiState.value =
                _uiState.value.copy(
                    aiTranscript = _uiState.value.aiTranscript + parsed.cleanedText
                )
            val target = parsed.focusTarget ?: ObjectMentionResolver.resolve(parsed.cleanedText)
            target?.let {
                maybeFocusFromMarker(target)
            }
        }

        geminiService.onDisconnected = { reason ->
            if (_uiState.value.isGeminiActive) {
                stopSession()
                _uiState.value = _uiState.value.copy(
                    errorMessage = "Connection lost: ${reason ?: "Unknown error"}"
                )
            }
        }

        // Check OpenClaw and start session
        viewModelScope.launch {
            openClawBridge.checkConnection()
            openClawBridge.resetSession()

            // Wire tool call handling
            toolCallRouter =
                ToolCallRouter(
                    bridge = openClawBridge,
                    scope = viewModelScope,
                    visionToolClient = visionToolClient,
                    latestFrameProvider = { latestVideoFrame },
                    onDetectionOverlay = { overlay ->
                        val currentQuery = _uiState.value.focusState.query ?: overlay?.query
                        _uiState.value =
                            _uiState.value.copy(
                                detectionOverlay = overlay,
                                focusState =
                                    if (overlay != null && currentQuery != null) {
                                        FocusState.fromOverlay(currentQuery, overlay)
                                    } else {
                                        FocusState()
                                    },
                            )
                        if (overlay != null) {
                            startTrackingLoop(overlay)
                        } else {
                            stopTrackingLoop()
                        }
                    },
                    onGuidanceSession = { session ->
                        _uiState.value = _uiState.value.copy(guidanceSession = session)
                    },
                    onFocusState = { focusState ->
                        _uiState.value = _uiState.value.copy(focusState = focusState)
                    },
                    onObjectInfoPanel = { panel ->
                        _uiState.value = _uiState.value.copy(objectInfoPanel = panel)
                    },
                )

            geminiService.onToolCall = { toolCall ->
                for (call in toolCall.functionCalls) {
                    toolCallRouter?.handleToolCall(call) { response ->
                        geminiService.sendToolResponse(response)
                    }
                }
            }

            geminiService.onToolCallCancellation = { cancellation ->
                toolCallRouter?.cancelToolCalls(cancellation.ids)
            }

            // Observe service state
            stateObservationJob = viewModelScope.launch {
                while (isActive) {
                    delay(100)
                    _uiState.value = _uiState.value.copy(
                        connectionState = geminiService.connectionState.value,
                        isModelSpeaking = geminiService.isModelSpeaking.value,
                        toolCallStatus = openClawBridge.lastToolCallStatus.value,
                        openClawConnectionState = openClawBridge.connectionState.value,
                    )
                }
            }

            // Connect to Gemini
            geminiService.connect { setupOk ->
                if (!setupOk) {
                    val msg = when (val state = geminiService.connectionState.value) {
                        is GeminiConnectionState.Error -> state.message
                        else -> "Failed to connect to Gemini"
                    }
                    _uiState.value = _uiState.value.copy(errorMessage = msg)
                    geminiService.disconnect()
                    stateObservationJob?.cancel()
                    _uiState.value = _uiState.value.copy(
                        isGeminiActive = false,
                        connectionState = GeminiConnectionState.Disconnected
                    )
                    return@connect
                }

                // Start mic capture
                try {
                    audioManager.startCapture()
                } catch (e: Exception) {
                    _uiState.value = _uiState.value.copy(
                        errorMessage = "Mic capture failed: ${e.message}"
                    )
                    geminiService.disconnect()
                    stateObservationJob?.cancel()
                    _uiState.value = _uiState.value.copy(
                        isGeminiActive = false,
                        connectionState = GeminiConnectionState.Disconnected
                    )
                }

                // Keep the live demo path narrow: no background event-stream reconnect noise
                if (SettingsManager.proactiveNotificationsEnabled) {
                    eventClient.onNotification = { text ->
                        val state = _uiState.value
                        if (state.isGeminiActive && state.connectionState == GeminiConnectionState.Ready) {
                            geminiService.sendTextMessage(text)
                        }
                    }
                    eventClient.connect()
                }
            }
        }

        startOverlayMaintenanceLoop()
    }

    fun stopSession() {
        eventClient.disconnect()
        toolCallRouter?.cancelAll()
        toolCallRouter = null
        audioManager.stopCapture()
        geminiService.disconnect()
        stateObservationJob?.cancel()
        stateObservationJob = null
        overlayMaintenanceJob?.cancel()
        overlayMaintenanceJob = null
        stopTrackingLoop()
        latestVideoFrame = null
        _uiState.value = GeminiUiState()
    }

    fun sendVideoFrameIfThrottled(bitmap: Bitmap) {
        latestVideoFrame = bitmap
        if (!SettingsManager.videoStreamingEnabled) return
        if (!_uiState.value.isGeminiActive) return
        if (_uiState.value.connectionState != GeminiConnectionState.Ready) return
        val now = System.currentTimeMillis()
        if (now - lastVideoFrameTime < GeminiConfig.VIDEO_FRAME_INTERVAL_MS) return
        lastVideoFrameTime = now
        geminiService.sendVideoFrame(bitmap)
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }

    fun clearDetectionOverlay() {
        _uiState.value = _uiState.value.copy(detectionOverlay = null)
        stopTrackingLoop()
    }

    fun hideObjectInfoPanel() {
        _uiState.value = _uiState.value.copy(objectInfoPanel = ObjectInfoPanelState())
    }

    private fun maybeFocusFromMarker(query: String) {
        val now = System.currentTimeMillis()
        val currentFocus = _uiState.value.focusState.query
        if (currentFocus.equals(query, ignoreCase = true)) return
        if (now - lastMarkerFocusAtMs < 2_500) return
        val frame = latestVideoFrame ?: return
        if (_uiState.value.connectionState != GeminiConnectionState.Ready) return
        lastMarkerFocusAtMs = now

        viewModelScope.launch {
            try {
                Log.d(TAG, "Auto focus from marker query='$query'")
                val detection = visionToolClient.locateObject(frame, query, false)
                val overlay = detection.toOverlay(frame.width, frame.height)
                _uiState.value =
                    _uiState.value.copy(
                        detectionOverlay = overlay,
                        focusState =
                            if (overlay != null) {
                                FocusState.fromOverlay(query, overlay)
                            } else {
                                FocusState()
                            },
                    )
                if (overlay != null) {
                    startTrackingLoop(overlay)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Auto focus from marker failed for '$query': ${e.message}", e)
            }
        }
    }

    private fun startTrackingLoop(initialOverlay: DetectionOverlay) {
        trackingJob?.cancel()
        trackingJob =
            viewModelScope.launch {
                var currentOverlay: DetectionOverlay? = initialOverlay
                var consecutiveMisses = 0
                while (isActive) {
                    delay(250)
                    val overlay = currentOverlay ?: break
                    val frame = latestVideoFrame ?: continue
                    if (!_uiState.value.isGeminiActive) continue
                    if (_uiState.value.connectionState != GeminiConnectionState.Ready) continue
                    try {
                        val tracked =
                            visionToolClient.trackTarget(
                                bitmap = frame,
                                query = overlay.query,
                                previousBbox = overlay.bbox.toJSON(),
                            )
                        if (tracked.found) {
                            val updatedOverlay = tracked.toOverlay(frame.width, frame.height)
                            consecutiveMisses = 0
                            currentOverlay = updatedOverlay
                            _uiState.value =
                                _uiState.value.copy(
                                    detectionOverlay = updatedOverlay,
                                    focusState =
                                        if (updatedOverlay != null) {
                                            FocusState.fromOverlay(updatedOverlay.query, updatedOverlay)
                                        } else {
                                            FocusState()
                                        },
                                )
                        } else {
                            consecutiveMisses += 1
                            if (consecutiveMisses >= 3) {
                                _uiState.value = _uiState.value.copy(detectionOverlay = null, focusState = FocusState())
                                currentOverlay = null
                            }
                        }
                    } catch (e: Exception) {
                        Log.e(TAG, "Tracking update failed: ${e.message}", e)
                    }
                }
            }
    }

    private fun stopTrackingLoop() {
        trackingJob?.cancel()
        trackingJob = null
    }

    private fun startOverlayMaintenanceLoop() {
        overlayMaintenanceJob?.cancel()
        overlayMaintenanceJob =
            viewModelScope.launch {
                while (isActive) {
                    delay(200)
                    val overlay = _uiState.value.detectionOverlay ?: continue
                    val ageMs = System.currentTimeMillis() - overlay.lastUpdatedAtMs
                    if (ageMs > 1_000) {
                        if (overlay.staleSinceMs == null) {
                            _uiState.value =
                                _uiState.value.copy(
                                    detectionOverlay = overlay.withStaleSince(System.currentTimeMillis())
                                )
                        } else {
                            val staleFor = System.currentTimeMillis() - overlay.staleSinceMs
                            if (staleFor > 5_000) {
                                Log.d(TAG, "Clearing stale overlay ageMs=$ageMs staleFor=$staleFor")
                                _uiState.value = _uiState.value.copy(detectionOverlay = null, focusState = FocusState())
                                stopTrackingLoop()
                            }
                        }
                    }
                }
            }
    }

    override fun onCleared() {
        super.onCleared()
        stopSession()
    }
}
