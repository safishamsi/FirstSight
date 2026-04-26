package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Save
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.meta.wearable.dat.externalsampleapps.cameraaccess.settings.SettingsManager

@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    fun loadDraft(): AgentProfileDraft = AgentProfileDraft.fromSettings()

    var draft by remember { mutableStateOf(loadDraft()) }
    var backendUserId by remember { mutableStateOf(SettingsManager.backendUserId) }
    var openClawHost by remember { mutableStateOf(SettingsManager.openClawHost) }
    var openClawPort by remember { mutableStateOf(SettingsManager.openClawPort.toString()) }
    var openClawHookToken by remember { mutableStateOf(SettingsManager.openClawHookToken) }
    var openClawGatewayToken by remember { mutableStateOf(SettingsManager.openClawGatewayToken) }
    var visionToolAuthToken by remember { mutableStateOf(SettingsManager.visionToolAuthToken) }
    var webrtcSignalingUrl by remember { mutableStateOf(SettingsManager.webrtcSignalingURL) }
    var backendFastWhisperDevice by remember { mutableStateOf(SettingsManager.backendFastWhisperDevice) }
    var showAdvanced by remember { mutableStateOf(false) }
    var showResetDialog by remember { mutableStateOf(false) }

    fun saveAndExit() {
        draft.saveToSettings()
        SettingsManager.backendUserId = backendUserId.trim()
        SettingsManager.openClawHost = openClawHost.trim()
        openClawPort.trim().toIntOrNull()?.let { SettingsManager.openClawPort = it }
        SettingsManager.openClawHookToken = openClawHookToken.trim()
        SettingsManager.openClawGatewayToken = openClawGatewayToken.trim()
        SettingsManager.visionToolAuthToken = visionToolAuthToken.trim()
        SettingsManager.webrtcSignalingURL = webrtcSignalingUrl.trim()
        SettingsManager.backendFastWhisperDevice = backendFastWhisperDevice.trim().ifBlank { "cpu" }
        onBack()
    }

    OpsScreen(modifier = modifier) {
        Column(modifier = Modifier.fillMaxSize()) {
            OpsTopBar(
                title = "AGENT CONFIG",
                subtitle = "Map the product-facing agent surface back to the current runtime primitives.",
                leading = {
                    OpsIconAction(onClick = ::saveAndExit) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back",
                            tint = OpsColor.Ink,
                        )
                    }
                },
                trailing = {
                    OpsIconAction(onClick = ::saveAndExit) {
                        Icon(
                            imageVector = Icons.Default.Save,
                            contentDescription = "Save",
                            tint = OpsColor.Accent,
                        )
                    }
                },
            )

            Column(
                modifier =
                    Modifier
                        .weight(1f)
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = 16.dp)
                        .navigationBarsPadding(),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                OpsPanel {
                    OpsSectionHeader("Profile Status")
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OpsTag(
                            label = if (draft.backendBaseUrl.isBlank()) "Status Draft" else "Status Ready",
                            background = if (draft.backendBaseUrl.isBlank()) OpsColor.Warning else OpsColor.Success,
                        )
                        OpsTag(
                            label =
                                when (draft.runtimeProfile) {
                                    AgentRuntimeProfile.REALTIME -> "Runtime Realtime"
                                    AgentRuntimeProfile.PIPELINE -> "Runtime Pipeline"
                                    AgentRuntimeProfile.DIRECT_GEMINI -> "Runtime Direct Gemini"
                                },
                            background = Color(0xFFEDEDED),
                        )
                    }
                    OpsBodyText(text = draft.runtimeProfile.summary)
                }

                OpsPanel {
                    OpsSectionHeader("Identity")
                    OpsTextField(
                        value = draft.name,
                        onValueChange = { draft = draft.copy(name = it) },
                        label = "Name",
                    )
                    OpsTextField(
                        value = draft.systemPrompt,
                        onValueChange = { draft = draft.copy(systemPrompt = it) },
                        label = "System Prompt",
                        singleLine = false,
                        minLines = 8,
                    )
                }

                OpsPanel {
                    OpsSectionHeader("Guidebook + Knowledge")
                    OpsTextField(
                        value = draft.guidebookTitle,
                        onValueChange = { draft = draft.copy(guidebookTitle = it) },
                        label = "Attached Guidebook",
                    )
                    OpsTextField(
                        value = draft.knowledgeSourceLabel,
                        onValueChange = { draft = draft.copy(knowledgeSourceLabel = it) },
                        label = "Knowledge Source Label",
                    )
                    OpsTextField(
                        value = draft.knowledgeEndpoint,
                        onValueChange = { draft = draft.copy(knowledgeEndpoint = it) },
                        label = "Knowledge Endpoint",
                        keyboardType = KeyboardType.Uri,
                    )
                }

                OpsPanel {
                    OpsSectionHeader("Runtime Stack")
                    OpsChoiceRow(
                        options = AgentRuntimeProfile.entries.map { it.title },
                        selected = draft.runtimeProfile.title,
                        onSelected = { selected ->
                            draft =
                                draft.copy(
                                    runtimeProfile =
                                        AgentRuntimeProfile.entries.first { it.title == selected },
                                )
                        },
                    )
                    OpsTextField(
                        value = draft.backendBaseUrl,
                        onValueChange = { draft = draft.copy(backendBaseUrl = it) },
                        label = "Backend Base URL",
                        keyboardType = KeyboardType.Uri,
                    )
                    OpsTextField(
                        value = backendUserId,
                        onValueChange = { backendUserId = it },
                        label = "User ID",
                    )
                    OpsTextField(
                        value = draft.userName,
                        onValueChange = { draft = draft.copy(userName = it) },
                        label = "Display Name",
                    )
                }

                OpsPanel {
                    OpsSectionHeader("Processors + Turn Logic")
                    OpsSwitchRow(
                        label = "Pose / Spatial Processor",
                        checked = draft.processorEnabled,
                        onCheckedChange = { draft = draft.copy(processorEnabled = it) },
                        detail = "Turns the backend pose processor on for augmented overlays and spatial annotations.",
                    )
                    OpsSwitchRow(
                        label = "Backend TTS",
                        checked = draft.ttsEnabled,
                        onCheckedChange = { draft = draft.copy(ttsEnabled = it) },
                        detail = "Controls whether the backend synthesizes spoken output for the agent.",
                    )
                    OpsSwitchRow(
                        label = "Proactive Notifications",
                        checked = draft.proactiveNotificationsEnabled,
                        onCheckedChange = { draft = draft.copy(proactiveNotificationsEnabled = it) },
                        detail = "Allows the runtime to surface more autonomous updates when enabled.",
                    )
                    OpsTextField(
                        value = draft.turnDelayMs,
                        onValueChange = { draft = draft.copy(turnDelayMs = it) },
                        label = "Smart Turn Delay (ms)",
                        keyboardType = KeyboardType.Number,
                    )
                    OpsTextField(
                        value = draft.geminiModel,
                        onValueChange = { draft = draft.copy(geminiModel = it) },
                        label = "Gemini Model",
                    )
                    OpsTextField(
                        value = draft.whisperModelSize,
                        onValueChange = { draft = draft.copy(whisperModelSize = it) },
                        label = "Whisper Model Size",
                    )
                    OpsTextField(
                        value = backendFastWhisperDevice,
                        onValueChange = { backendFastWhisperDevice = it },
                        label = "Whisper Device",
                    )
                }

                OpsPanel {
                    OpsSectionHeader("Tools")
                    OpsBodyText(text = "The built-in primitives remain part of the app contract. These switches store the frontend profile shape and line up with the current backend toggles where available.")
                    draft.tools.forEach { tool ->
                        OpsSwitchRow(
                            label = tool.label,
                            checked = tool.enabled,
                            onCheckedChange = { enabled ->
                                draft =
                                    draft.copy(
                                        tools =
                                            draft.tools.map { existing ->
                                                if (existing.persistentKey == tool.persistentKey) {
                                                    existing.copy(enabled = enabled)
                                                } else {
                                                    existing
                                                }
                                            },
                                    )
                            },
                        )
                    }
                }

                OpsPanel {
                    OpsSectionHeader("Interaction")
                    OpsChoiceRow(
                        options = TriggerMode.entries.map { it.label },
                        selected = draft.triggerMode.label,
                        onSelected = { selected ->
                            draft =
                                draft.copy(
                                    triggerMode = TriggerMode.entries.first { it.label == selected },
                                )
                        },
                    )
                    OpsSwitchRow(
                        label = "Voice Synthesis",
                        checked = draft.outputVoiceEnabled,
                        onCheckedChange = { draft = draft.copy(outputVoiceEnabled = it) },
                    )
                    OpsSwitchRow(
                        label = "HUD Overlay Data",
                        checked = draft.outputOverlayEnabled,
                        onCheckedChange = { draft = draft.copy(outputOverlayEnabled = it) },
                    )
                }

                OpsPanel {
                    OpsSectionHeader(
                        "Advanced Wiring",
                        trailing = {
                            OpsSecondaryButton(
                                label = if (showAdvanced) "Hide" else "Show",
                                onClick = { showAdvanced = !showAdvanced },
                            )
                        },
                    )
                    OpsBodyText(text = "These fields are still exposed because the current app runtime depends on them directly.")
                    if (showAdvanced) {
                        OpsTextField(
                            value = openClawHost,
                            onValueChange = { openClawHost = it },
                            label = "OpenClaw Host",
                            keyboardType = KeyboardType.Uri,
                        )
                        OpsTextField(
                            value = openClawPort,
                            onValueChange = { openClawPort = it },
                            label = "OpenClaw Port",
                            keyboardType = KeyboardType.Number,
                        )
                        OpsTextField(
                            value = openClawHookToken,
                            onValueChange = { openClawHookToken = it },
                            label = "OpenClaw Hook Token",
                        )
                        OpsTextField(
                            value = openClawGatewayToken,
                            onValueChange = { openClawGatewayToken = it },
                            label = "OpenClaw Gateway Token",
                        )
                        OpsTextField(
                            value = visionToolAuthToken,
                            onValueChange = { visionToolAuthToken = it },
                            label = "Vision Tool Auth Token",
                        )
                        OpsTextField(
                            value = webrtcSignalingUrl,
                            onValueChange = { webrtcSignalingUrl = it },
                            label = "WebRTC Signaling URL",
                            keyboardType = KeyboardType.Uri,
                        )
                    }
                }

                OpsPanel {
                    OpsSectionHeader("Reset")
                    OpsBodyText(text = "Reset returns this screen to the baked-in defaults from the app and secrets file.")
                    OpsPrimaryButton(
                        label = "Reset All",
                        onClick = { showResetDialog = true },
                        isDestructive = true,
                    )
                }
            }
        }
    }

    if (showResetDialog) {
        AlertDialog(
            onDismissRequest = { showResetDialog = false },
            title = { Text("Reset settings?") },
            text = { Text("This clears all saved agent and runtime settings from the app.") },
            confirmButton = {
                OpsPrimaryButton(
                    label = "Reset",
                    onClick = {
                        SettingsManager.resetAll()
                        draft = loadDraft()
                        backendUserId = SettingsManager.backendUserId
                        openClawHost = SettingsManager.openClawHost
                        openClawPort = SettingsManager.openClawPort.toString()
                        openClawHookToken = SettingsManager.openClawHookToken
                        openClawGatewayToken = SettingsManager.openClawGatewayToken
                        visionToolAuthToken = SettingsManager.visionToolAuthToken
                        webrtcSignalingUrl = SettingsManager.webrtcSignalingURL
                        backendFastWhisperDevice = SettingsManager.backendFastWhisperDevice
                        showResetDialog = false
                    },
                    isDestructive = true,
                )
            },
            dismissButton = {
                OpsSecondaryButton(
                    label = "Cancel",
                    onClick = { showResetDialog = false },
                )
            },
        )
    }
}
