package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentConnectionState
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentUiState

@Composable
fun VisionAgentOverlay(
    uiState: VisionAgentUiState,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxWidth().padding(horizontal = 16.dp),
    ) {
        VisionAgentStatusBar(connectionState = uiState.connectionState)

        if (uiState.activeProtocolTitle != null || uiState.checklistItems.isNotEmpty()) {
            Spacer(modifier = Modifier.height(8.dp))
            VisionAgentChecklistCard(uiState = uiState)
        }

        if (uiState.transcriptHistory.isNotEmpty()) {
            Spacer(modifier = Modifier.height(8.dp))
            val lastTurn = uiState.transcriptHistory.last()
            TranscriptView(
                userTranscript = lastTurn.userText,
                aiTranscript = lastTurn.assistantText,
            )
        }

        if (uiState.userTranscript.isNotBlank() || uiState.assistantTranscript.isNotBlank()) {
            Spacer(modifier = Modifier.height(8.dp))
            TranscriptView(
                userTranscript = uiState.userTranscript,
                aiTranscript = uiState.assistantTranscript,
            )
        }
    }
}

@Composable
fun VisionAgentDebugPanel(
    uiState: VisionAgentUiState,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(Color.Black.copy(alpha = 0.55f), RoundedCornerShape(8.dp))
            .border(1.dp, Color.White.copy(alpha = 0.20f))
            .padding(horizontal = 12.dp, vertical = 8.dp),
    ) {
        Text(
            text = "Vision Agent Debug",
            color = Color.White,
            style = MaterialTheme.typography.titleSmall,
        )
        Spacer(modifier = Modifier.height(6.dp))
        VisionAgentDebugLine("State", visionAgentConnectionLabel(uiState.connectionState))
        uiState.provider?.let { VisionAgentDebugLine("Provider", it) }
        uiState.callId?.let { VisionAgentDebugLine("Call", it) }
        uiState.agentSessionId?.let { VisionAgentDebugLine("Agent", it) }
        uiState.activeProtocolTitle?.let { VisionAgentDebugLine("Protocol", it) }
        uiState.currentChecklistStep?.let { VisionAgentDebugLine("Checklist", it) }
        uiState.activeProtocolSummary?.let { VisionAgentDebugLine("Guide", it) }
        VisionAgentDebugLine("Frames", uiState.videoFrames.toString())
        VisionAgentDebugLine("Audio", uiState.audioChunks.toString())
        if (uiState.visionAgentError != null) {
            VisionAgentDebugLine("Bootstrap", uiState.visionAgentError)
        }
    }
}

@Composable
private fun VisionAgentStatusBar(
    connectionState: VisionAgentConnectionState,
    modifier: Modifier = Modifier,
) {
    StatusPill(
        label = "Vision Agent",
        color = when (connectionState) {
            is VisionAgentConnectionState.Ready -> Color(0xFF4CAF50)
            is VisionAgentConnectionState.Bootstrapping,
            is VisionAgentConnectionState.Connecting -> Color(0xFFFF9800)
            is VisionAgentConnectionState.Error -> Color(0xFFF44336)
            is VisionAgentConnectionState.Disconnected -> Color(0xFF9E9E9E)
        },
        modifier = modifier,
    )
}

@Composable
private fun VisionAgentDebugLine(
    label: String,
    value: String,
) {
    Text(
        text = "$label: $value",
        color = Color.White,
        fontSize = 12.sp,
        maxLines = 2,
        overflow = TextOverflow.Ellipsis,
    )
}

@Composable
private fun VisionAgentChecklistCard(
    uiState: VisionAgentUiState,
) {
    Column(
        modifier =
            Modifier
                .fillMaxWidth()
                .background(Color.Black.copy(alpha = 0.58f), RoundedCornerShape(10.dp))
                .border(1.dp, Color.White.copy(alpha = 0.20f))
                .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        uiState.activeProtocolTitle?.let { title ->
            Text(
                text = title,
                color = Color.White,
                style = MaterialTheme.typography.titleSmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        uiState.currentChecklistStep?.let { step ->
            Text(
                text = "Now: $step",
                color = Color(0xFFE3F2FD),
                fontSize = 13.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
        if (uiState.riskFlags.isNotEmpty()) {
            Text(
                text = "Flags: ${uiState.riskFlags.joinToString(", ")}",
                color = Color(0xFFFFCC80),
                fontSize = 12.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
        uiState.checklistItems.take(3).forEach { item ->
            Row(
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    text = checklistBulletFor(item.status),
                    color = checklistColorFor(item.status),
                    fontSize = 13.sp,
                )
                Text(
                    text = item.label,
                    color = Color.White,
                    fontSize = 13.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(start = 8.dp),
                )
            }
        }
        val guidePreview =
            uiState.activeProtocolSummary
                ?: uiState.activeProtocolManual
                    ?.lineSequence()
                    ?.map { it.trim() }
                    ?.firstOrNull { it.isNotBlank() && !it.startsWith("#") }
        if (!guidePreview.isNullOrBlank()) {
            Text(
                text = guidePreview,
                color = Color(0xFFCFD8DC),
                fontSize = 12.sp,
                maxLines = 4,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

private fun checklistBulletFor(status: String): String =
    when (status) {
        "done" -> "DONE"
        "active" -> "NOW"
        "blocked" -> "HOLD"
        else -> "NEXT"
    }

private fun checklistColorFor(status: String): Color =
    when (status) {
        "done" -> Color(0xFF81C784)
        "active" -> Color(0xFF4FC3F7)
        "blocked" -> Color(0xFFE57373)
        else -> Color(0xFFB0BEC5)
    }

private fun visionAgentConnectionLabel(connectionState: VisionAgentConnectionState): String =
    when (connectionState) {
        VisionAgentConnectionState.Bootstrapping -> "Bootstrapping session"
        VisionAgentConnectionState.Connecting -> "Connecting websocket"
        VisionAgentConnectionState.Ready -> "Streaming to backend"
        VisionAgentConnectionState.Disconnected -> "Disconnected"
        is VisionAgentConnectionState.Error -> connectionState.message
    }
