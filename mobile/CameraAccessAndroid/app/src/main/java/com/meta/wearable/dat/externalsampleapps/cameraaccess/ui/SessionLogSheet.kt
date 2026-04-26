package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.meta.wearable.dat.externalsampleapps.cameraaccess.gemini.GeminiUiState
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentUiState
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentMode

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionLogSheet(
    mode: VisionAgentMode,
    geminiUiState: GeminiUiState,
    visionAgentUiState: VisionAgentUiState,
    onRunCurrentCheck: () -> Unit,
    onAdvanceChecklist: () -> Unit,
    onMarkSpeechNormal: () -> Unit,
    onMarkSpeechSlurred: () -> Unit,
    onClearGuide: () -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
    ) {
        Column(
            modifier =
                modifier
                    .fillMaxWidth()
                    .fillMaxHeight(0.88f)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 20.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            OpsPanel {
                OpsSectionHeader("Live Session")
                OpsTag(
                    label =
                        when (mode) {
                            VisionAgentMode.DIRECT_GEMINI -> "Gemini Lab"
                            VisionAgentMode.VISION_AGENT_BACKEND -> "Vision Backend"
                        },
                    background = OpsColor.AccentSoft,
                )
                OpsBodyText(
                    text = "The augmented video remains primary. This drawer holds the transcript log, checklist state, and runtime wiring details.",
                )
            }

            if (mode == VisionAgentMode.VISION_AGENT_BACKEND) {
                OpsPanel {
                    OpsSectionHeader("Backend State")
                    visionAgentUiState.sessionId?.let { OpsBodyText(text = "Session ID: $it", muted = false) }
                    visionAgentUiState.callId?.let { OpsBodyText(text = "Call ID: $it", muted = false) }
                    visionAgentUiState.agentSessionId?.let { OpsBodyText(text = "Agent Session: $it", muted = false) }
                    visionAgentUiState.activeProtocolTitle?.let { OpsBodyText(text = "Guidebook: $it", muted = false) }
                    visionAgentUiState.currentChecklistStep?.let { OpsBodyText(text = "Current Step: $it", muted = false) }
                    if (visionAgentUiState.riskFlags.isNotEmpty()) {
                        OpsBodyText(text = "Flags: ${visionAgentUiState.riskFlags.joinToString(", ")}", muted = false)
                    }
                    if (visionAgentUiState.checklistItems.isEmpty()) {
                        OpsBodyText(text = "No checklist items loaded into the active session yet.")
                    } else {
                        visionAgentUiState.checklistItems.forEach { item ->
                            OpsBodyText(text = "${item.status.uppercase()}: ${item.label}", muted = false)
                        }
                    }
                }

                val activeStep =
                    visionAgentUiState.checklistItems.firstOrNull { it.status == "active" }
                        ?: visionAgentUiState.checklistItems.firstOrNull { it.status == "pending" }
                val isStrokeDemo = visionAgentUiState.activeProtocolTitle == "Stroke FAST Check"
                if (isStrokeDemo && activeStep != null) {
                    OpsPanel {
                        OpsSectionHeader("Stroke Demo Controls")
                        OpsBodyText(text = "Use these controls to drive the 3-step stroke check reliably during the demo.")
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            if (activeStep.kind == "agent_tool_call") {
                                OpsPrimaryButton(
                                    label = "Run Check",
                                    onClick = onRunCurrentCheck,
                                    modifier = Modifier.weight(1f),
                                )
                            } else {
                                OpsPrimaryButton(
                                    label = "Next Step",
                                    onClick = onAdvanceChecklist,
                                    modifier = Modifier.weight(1f),
                                )
                            }
                            OpsSecondaryButton(
                                label = "Clear Guide",
                                onClick = onClearGuide,
                                modifier = Modifier.weight(1f),
                            )
                        }
                        if (activeStep.id == "is_speech_slurred") {
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                OpsSecondaryButton(
                                    label = "Speech Normal",
                                    onClick = onMarkSpeechNormal,
                                    modifier = Modifier.weight(1f),
                                )
                                OpsPrimaryButton(
                                    label = "Speech Slurred",
                                    onClick = onMarkSpeechSlurred,
                                    modifier = Modifier.weight(1f),
                                )
                            }
                        }
                    }
                }

                OpsPanel {
                    OpsSectionHeader("Transcript Log")
                    if (visionAgentUiState.transcriptHistory.isEmpty() &&
                        visionAgentUiState.userTranscript.isBlank() &&
                        visionAgentUiState.assistantTranscript.isBlank()
                    ) {
                        OpsBodyText(text = "No transcript turns captured yet.")
                    } else {
                        visionAgentUiState.transcriptHistory.reversed().forEach { turn ->
                            OpsBodyText(text = "USER: ${turn.userText}", muted = false)
                            OpsBodyText(text = "AGENT: ${turn.assistantText}", muted = false)
                        }
                        if (visionAgentUiState.userTranscript.isNotBlank()) {
                            OpsBodyText(text = "USER: ${visionAgentUiState.userTranscript}", muted = false)
                        }
                        if (visionAgentUiState.assistantTranscript.isNotBlank()) {
                            OpsBodyText(text = "AGENT: ${visionAgentUiState.assistantTranscript}", muted = false)
                        }
                    }
                }
            } else {
                OpsPanel {
                    OpsSectionHeader("Gemini State")
                    OpsBodyText(text = "Connection: ${geminiUiState.connectionState}", muted = false)
                    if (geminiUiState.guidanceSession.isActive) {
                        OpsBodyText(text = "Guidance Task: ${geminiUiState.guidanceSession.task}", muted = false)
                        OpsBodyText(text = "Step ${geminiUiState.guidanceSession.stepIndex}: ${geminiUiState.guidanceSession.stepTitle}", muted = false)
                    }
                    OpsBodyText(
                        text =
                            if (geminiUiState.userTranscript.isBlank() && geminiUiState.aiTranscript.isBlank()) {
                                "No transcript captured yet."
                            } else {
                                "USER: ${geminiUiState.userTranscript}\nAGENT: ${geminiUiState.aiTranscript}"
                            },
                        muted = false,
                    )
                }
            }
        }
    }
}
