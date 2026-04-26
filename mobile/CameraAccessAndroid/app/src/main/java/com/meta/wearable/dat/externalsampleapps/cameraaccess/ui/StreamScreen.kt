package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.compose.foundation.clickable
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.meta.wearable.dat.camera.types.StreamSessionState
import com.meta.wearable.dat.externalsampleapps.cameraaccess.R
import com.meta.wearable.dat.externalsampleapps.cameraaccess.gemini.GeminiSessionViewModel
import com.meta.wearable.dat.externalsampleapps.cameraaccess.settings.SettingsManager
import com.meta.wearable.dat.externalsampleapps.cameraaccess.stream.StreamViewModel
import com.meta.wearable.dat.externalsampleapps.cameraaccess.stream.StreamingMode
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentMode
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentSessionViewModel
import com.meta.wearable.dat.externalsampleapps.cameraaccess.wearables.WearablesViewModel
import com.meta.wearable.dat.externalsampleapps.cameraaccess.webrtc.WebRTCSessionViewModel

@Composable
fun StreamScreen(
    wearablesViewModel: WearablesViewModel,
    isPhoneMode: Boolean = false,
    modifier: Modifier = Modifier,
    streamViewModel: StreamViewModel =
        viewModel(
            factory =
                StreamViewModel.Factory(
                    application = (LocalActivity.current as ComponentActivity).application,
                    wearablesViewModel = wearablesViewModel,
                ),
        ),
    geminiViewModel: GeminiSessionViewModel = viewModel(),
    visionAgentViewModel: VisionAgentSessionViewModel = viewModel(),
    webrtcViewModel: WebRTCSessionViewModel = viewModel(),
) {
    var aiMode by remember { mutableStateOf(SettingsManager.aiBackendMode) }
    var showVisionAgentDebugPanel by remember { mutableStateOf(false) }
    var showGuideBrowser by remember { mutableStateOf(false) }
    var showVisionAgentArtifacts by remember { mutableStateOf(true) }
    var showSessionLog by remember { mutableStateOf(false) }
    val streamUiState by streamViewModel.uiState.collectAsStateWithLifecycle()
    val geminiUiState by geminiViewModel.uiState.collectAsStateWithLifecycle()
    val visionAgentUiState by visionAgentViewModel.uiState.collectAsStateWithLifecycle()
    val webrtcUiState by webrtcViewModel.uiState.collectAsStateWithLifecycle()
    val lifecycleOwner = LocalLifecycleOwner.current
    val context = LocalContext.current

    LaunchedEffect(geminiViewModel) {
        streamViewModel.geminiViewModel = geminiViewModel
    }
    LaunchedEffect(visionAgentViewModel) {
        streamViewModel.visionAgentViewModel = visionAgentViewModel
    }
    LaunchedEffect(webrtcViewModel) {
        streamViewModel.webrtcViewModel = webrtcViewModel
    }

    LaunchedEffect(isPhoneMode) {
        if (isPhoneMode) {
            geminiViewModel.streamingMode = StreamingMode.PHONE
            visionAgentViewModel.streamingMode = StreamingMode.PHONE
            streamViewModel.startPhoneCamera(lifecycleOwner)
        } else {
            geminiViewModel.streamingMode = StreamingMode.GLASSES
            visionAgentViewModel.streamingMode = StreamingMode.GLASSES
            streamViewModel.startStream()
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            if (geminiUiState.isGeminiActive) {
                geminiViewModel.stopSession()
            } else {
                geminiViewModel.clearDetectionOverlay()
            }
            if (visionAgentUiState.isVisionAgentActive) {
                visionAgentViewModel.stopSession()
            }
            if (webrtcUiState.isActive) {
                webrtcViewModel.stopSession()
            }
        }
    }

    LaunchedEffect(geminiUiState.errorMessage) {
        geminiUiState.errorMessage?.let { msg ->
            Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
            geminiViewModel.clearError()
        }
    }
    LaunchedEffect(visionAgentUiState.errorMessage) {
        visionAgentUiState.errorMessage?.let { msg ->
            Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
            visionAgentViewModel.clearError()
        }
    }
    LaunchedEffect(webrtcUiState.errorMessage) {
        webrtcUiState.errorMessage?.let { msg ->
            Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
            webrtcViewModel.clearError()
        }
    }

    Box(modifier = modifier.fillMaxSize().background(Color.Black)) {
        streamUiState.videoFrame?.let { videoFrame ->
            Image(
                bitmap = videoFrame.asImageBitmap(),
                contentDescription = stringResource(R.string.live_stream),
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop,
            )

            if (
                aiMode == VisionAgentMode.VISION_AGENT_BACKEND &&
                visionAgentUiState.isVisionAgentActive &&
                showVisionAgentArtifacts &&
                visionAgentUiState.spatialOverlays.isNotEmpty()
            ) {
                VisionAgentSpatialOverlays(
                    overlays = visionAgentUiState.spatialOverlays,
                    frameWidth = videoFrame.width,
                    frameHeight = videoFrame.height,
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }

        geminiUiState.detectionOverlay?.let { overlay ->
            ObjectDetectionOverlay(
                overlay = overlay,
                modifier = Modifier.fillMaxSize(),
            )
        }

        if (streamUiState.streamSessionState == StreamSessionState.STARTING) {
            CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
        }

        Box(modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp, vertical = 10.dp)) {
            Column(
                modifier =
                    Modifier
                        .align(Alignment.TopStart)
                        .statusBarsPadding(),
            ) {
                LiveSessionHeader(
                    agentName = SettingsManager.activeAgentName,
                    guidebookTitle = visionAgentUiState.activeProtocolTitle ?: SettingsManager.activeGuidebookTitle,
                    aiMode = aiMode,
                    onToggleArtifacts = { showVisionAgentArtifacts = !showVisionAgentArtifacts },
                    showArtifacts = showVisionAgentArtifacts,
                    onOpenGuideBrowser = { showGuideBrowser = true },
                    onOpenSessionLog = { showSessionLog = true },
                    onToggleDebug = { showVisionAgentDebugPanel = !showVisionAgentDebugPanel },
                    showDebugButton = aiMode == VisionAgentMode.VISION_AGENT_BACKEND,
                    onShowSettings = wearablesViewModel::showSettings,
                )

                Spacer(modifier = Modifier.height(8.dp))
                AiModeSwitcher(
                    mode = aiMode,
                    onModeSelected = { selectedMode ->
                        if (selectedMode != aiMode) {
                            if (geminiUiState.isGeminiActive) {
                                geminiViewModel.stopSession()
                            }
                            if (visionAgentUiState.isVisionAgentActive) {
                                visionAgentViewModel.stopSession()
                            }
                            geminiViewModel.clearDetectionOverlay()
                            SettingsManager.aiBackendMode = selectedMode
                            aiMode = selectedMode
                            showVisionAgentDebugPanel = false
                        }
                    },
                )

                if (aiMode == VisionAgentMode.DIRECT_GEMINI && geminiUiState.isGeminiActive) {
                    Spacer(modifier = Modifier.height(8.dp))
                    GeminiOverlay(uiState = geminiUiState)
                }
                if (aiMode == VisionAgentMode.VISION_AGENT_BACKEND && visionAgentUiState.isVisionAgentActive) {
                    Spacer(modifier = Modifier.height(8.dp))
                    VisionAgentOverlay(uiState = visionAgentUiState)
                    if (showVisionAgentDebugPanel) {
                        Spacer(modifier = Modifier.height(8.dp))
                        VisionAgentDebugPanel(uiState = visionAgentUiState)
                    }
                }
                if (webrtcUiState.isActive) {
                    Spacer(modifier = Modifier.height(8.dp))
                    WebRTCOverlay(uiState = webrtcUiState)
                }
                if (geminiUiState.objectInfoPanel.visible) {
                    Spacer(modifier = Modifier.height(8.dp))
                    ObjectInfoPanel(
                        state = geminiUiState.objectInfoPanel,
                        onDismiss = { geminiViewModel.hideObjectInfoPanel() },
                    )
                }
            }

            ControlsRow(
                onStopStream = {
                    if (geminiUiState.isGeminiActive) geminiViewModel.stopSession()
                    if (visionAgentUiState.isVisionAgentActive) visionAgentViewModel.stopSession()
                    geminiViewModel.clearDetectionOverlay()
                    if (webrtcUiState.isActive) webrtcViewModel.stopSession()
                    streamViewModel.stopStream()
                    wearablesViewModel.navigateToDeviceSelection()
                },
                onCapturePhoto = { streamViewModel.capturePhoto() },
                onToggleAI = {
                    when (aiMode) {
                        VisionAgentMode.DIRECT_GEMINI -> {
                            if (geminiUiState.isGeminiActive) {
                                geminiViewModel.stopSession()
                            } else {
                                visionAgentViewModel.stopSession()
                                geminiViewModel.startSession()
                            }
                        }
                        VisionAgentMode.VISION_AGENT_BACKEND -> {
                            if (visionAgentUiState.isVisionAgentActive) {
                                visionAgentViewModel.stopSession()
                            } else {
                                geminiViewModel.stopSession()
                                visionAgentViewModel.startSession()
                            }
                        }
                    }
                },
                isAIActive =
                    when (aiMode) {
                        VisionAgentMode.DIRECT_GEMINI -> geminiUiState.isGeminiActive
                        VisionAgentMode.VISION_AGENT_BACKEND -> visionAgentUiState.isVisionAgentActive
                    },
                onToggleLive = {
                    if (webrtcUiState.isActive) {
                        webrtcViewModel.stopSession()
                    } else {
                        webrtcViewModel.startSession()
                    }
                },
                isLiveActive = webrtcUiState.isActive,
                modifier = Modifier.align(Alignment.BottomCenter),
            )
        }
    }

    if (showGuideBrowser) {
        GuideBrowserSheet(
            activeSessionId = visionAgentUiState.sessionId,
            onLoadGuideIntoSession = { protocolId, matchedQuery, onComplete ->
                visionAgentViewModel.loadGuideIntoSession(
                    protocolId = protocolId,
                    matchedQuery = matchedQuery,
                    onComplete = onComplete,
                )
            },
            onClearGuideFromSession = { onComplete ->
                visionAgentViewModel.clearGuideFromSession(onComplete = onComplete)
            },
            onDismiss = { showGuideBrowser = false },
        )
    }

    if (showSessionLog) {
        SessionLogSheet(
            mode = aiMode,
            geminiUiState = geminiUiState,
            visionAgentUiState = visionAgentUiState,
            onRunCurrentCheck = {
                visionAgentViewModel.sendChecklistControlMessage("run the check now")
            },
            onAdvanceChecklist = {
                visionAgentViewModel.sendChecklistControlMessage("done, next step")
            },
            onMarkSpeechNormal = {
                visionAgentViewModel.sendChecklistControlMessage("speech sounds normal")
            },
            onMarkSpeechSlurred = {
                visionAgentViewModel.sendChecklistControlMessage("speech is slurred")
            },
            onClearGuide = {
                visionAgentViewModel.clearGuideFromSession()
            },
            onDismiss = { showSessionLog = false },
        )
    }

    streamUiState.capturedPhoto?.let { photo ->
        if (streamUiState.isShareDialogVisible) {
            SharePhotoDialog(
                photo = photo,
                onDismiss = { streamViewModel.hideShareDialog() },
                onShare = { bitmap ->
                    streamViewModel.sharePhoto(bitmap)
                    streamViewModel.hideShareDialog()
                },
            )
        }
    }
}

@Composable
private fun LiveSessionHeader(
    agentName: String,
    guidebookTitle: String,
    aiMode: VisionAgentMode,
    onToggleArtifacts: () -> Unit,
    showArtifacts: Boolean,
    onOpenGuideBrowser: () -> Unit,
    onOpenSessionLog: () -> Unit,
    onToggleDebug: () -> Unit,
    showDebugButton: Boolean,
    onShowSettings: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Top,
    ) {
        Column(
            modifier =
                Modifier
                    .background(OpsColor.Overlay, RoundedCornerShape(2.dp))
                    .padding(horizontal = 12.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = agentName.uppercase(),
                color = Color.White,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = if (aiMode == VisionAgentMode.VISION_AGENT_BACKEND) "LIVE STREAMING" else "GEMINI LAB STREAM",
                color = Color.White.copy(alpha = 0.75f),
                fontFamily = FontFamily.Monospace,
                fontSize = 11.sp,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                OpsTag(label = "LIVE", background = OpsColor.Warning)
                OpsTag(label = guidebookTitle, background = OpsColor.Accent, foreground = Color.White)
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            OverlayActionButton(
                label = "LOG",
                onClick = onOpenSessionLog,
            )
            if (aiMode == VisionAgentMode.VISION_AGENT_BACKEND) {
                OverlayActionButton(
                    label = if (showArtifacts) "HUD" else "RAW",
                    onClick = onToggleArtifacts,
                )
                OverlayActionButton(
                    label = "GUIDE",
                    onClick = onOpenGuideBrowser,
                )
                if (showDebugButton) {
                    OverlayActionButton(
                        label = "DBG",
                        onClick = onToggleDebug,
                    )
                }
            }
            OverlayActionButton(label = "SET", onClick = onShowSettings)
        }
    }
}

@Composable
private fun OverlayActionButton(
    label: String,
    onClick: () -> Unit,
) {
    Box(
        modifier =
            Modifier
                .background(OpsColor.Overlay, RoundedCornerShape(2.dp))
                .padding(horizontal = 10.dp, vertical = 9.dp)
                .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            color = Color.White,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
        )
    }
}
