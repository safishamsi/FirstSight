package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
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

private fun visionAgentConnectionLabel(connectionState: VisionAgentConnectionState): String =
    when (connectionState) {
        VisionAgentConnectionState.Bootstrapping -> "Bootstrapping session"
        VisionAgentConnectionState.Connecting -> "Connecting websocket"
        VisionAgentConnectionState.Ready -> "Streaming to backend"
        VisionAgentConnectionState.Disconnected -> "Disconnected"
        is VisionAgentConnectionState.Error -> connectionState.message
    }
