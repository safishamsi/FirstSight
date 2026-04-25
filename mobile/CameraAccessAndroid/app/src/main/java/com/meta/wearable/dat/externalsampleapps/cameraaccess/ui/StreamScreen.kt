/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BugReport
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.meta.wearable.dat.camera.types.StreamSessionState
import com.meta.wearable.dat.externalsampleapps.cameraaccess.R
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentMode
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentSessionViewModel
import com.meta.wearable.dat.externalsampleapps.cameraaccess.gemini.GeminiSessionViewModel
import com.meta.wearable.dat.externalsampleapps.cameraaccess.settings.SettingsManager
import com.meta.wearable.dat.externalsampleapps.cameraaccess.stream.StreamViewModel
import com.meta.wearable.dat.externalsampleapps.cameraaccess.stream.StreamingMode
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
    val streamUiState by streamViewModel.uiState.collectAsStateWithLifecycle()
    val geminiUiState by geminiViewModel.uiState.collectAsStateWithLifecycle()
    val visionAgentUiState by visionAgentViewModel.uiState.collectAsStateWithLifecycle()
    val webrtcUiState by webrtcViewModel.uiState.collectAsStateWithLifecycle()
    val lifecycleOwner = LocalLifecycleOwner.current
    val context = LocalContext.current

    // Wire Gemini VM to Stream VM for frame forwarding
    LaunchedEffect(geminiViewModel) {
        streamViewModel.geminiViewModel = geminiViewModel
    }

    // Wire Vision Agent VM to Stream VM for frame forwarding
    LaunchedEffect(visionAgentViewModel) {
        streamViewModel.visionAgentViewModel = visionAgentViewModel
    }

    // Wire WebRTC VM to Stream VM for frame forwarding
    LaunchedEffect(webrtcViewModel) {
        streamViewModel.webrtcViewModel = webrtcViewModel
    }

    // Start stream or phone camera
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

    // Clean up on exit
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

    // Show errors as toasts
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

    Box(modifier = modifier.fillMaxSize()) {
        // Video feed
        streamUiState.videoFrame?.let { videoFrame ->
            Image(
                bitmap = videoFrame.asImageBitmap(),
                contentDescription = stringResource(R.string.live_stream),
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop,
            )
        }

        geminiUiState.detectionOverlay?.let { overlay ->
            ObjectDetectionOverlay(
                overlay = overlay,
                modifier = Modifier.fillMaxSize(),
            )
        }

        if (streamUiState.streamSessionState == StreamSessionState.STARTING) {
            CircularProgressIndicator(
                modifier = Modifier.align(Alignment.Center),
            )
        }

        // Overlays + controls
        Box(modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
            // Top overlays (below status bar)
            Column(modifier = Modifier.align(Alignment.TopStart).statusBarsPadding().padding(top = 8.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    AiModeBadge(mode = aiMode)
                    Row {
                        if (aiMode == VisionAgentMode.VISION_AGENT_BACKEND) {
                            IconButton(
                                onClick = { showVisionAgentDebugPanel = !showVisionAgentDebugPanel },
                            ) {
                                Icon(
                                    imageVector = Icons.Default.BugReport,
                                    contentDescription = "Vision Agent debug",
                                    tint = androidx.compose.ui.graphics.Color.White,
                                    modifier = Modifier.size(28.dp),
                                )
                            }
                        }
                        IconButton(
                            onClick = { wearablesViewModel.showSettings() },
                        ) {
                            Icon(
                                imageVector = Icons.Default.Settings,
                                contentDescription = "Settings",
                                tint = androidx.compose.ui.graphics.Color.White,
                                modifier = Modifier.size(28.dp),
                            )
                        }
                    }
                }
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

                // Gemini overlay
                if (aiMode == VisionAgentMode.DIRECT_GEMINI && geminiUiState.isGeminiActive) {
                    Spacer(modifier = Modifier.height(4.dp))
                    GeminiOverlay(uiState = geminiUiState)
                }
                if (aiMode == VisionAgentMode.VISION_AGENT_BACKEND && visionAgentUiState.isVisionAgentActive) {
                    Spacer(modifier = Modifier.height(4.dp))
                    VisionAgentOverlay(uiState = visionAgentUiState)
                    if (showVisionAgentDebugPanel) {
                        Spacer(modifier = Modifier.height(4.dp))
                        VisionAgentDebugPanel(uiState = visionAgentUiState)
                    }
                }

                // WebRTC overlay
                if (webrtcUiState.isActive) {
                    Spacer(modifier = Modifier.height(4.dp))
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

            // Controls at bottom
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
                isAIActive = when (aiMode) {
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

    // Share photo dialog
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
