package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentConnectionState
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentUiState

@Composable
fun VisionAgentOverlay(
    uiState: VisionAgentUiState,
    modifier: Modifier = Modifier,
) {
    val statusColor = when (uiState.connectionState) {
        is VisionAgentConnectionState.Ready -> AppColor.Green
        is VisionAgentConnectionState.Error -> AppColor.Red
        VisionAgentConnectionState.Disconnected -> Color.Gray
        else -> AppColor.DeepBlue
    }

    Column(
        modifier = modifier
            .background(statusColor.copy(alpha = 0.9f), RoundedCornerShape(16.dp))
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Text(
            text = "Vision Agent Backend",
            style = MaterialTheme.typography.titleSmall,
            color = Color.White,
        )
        Text(
            text = when (uiState.connectionState) {
                VisionAgentConnectionState.Bootstrapping -> "Bootstrapping session"
                VisionAgentConnectionState.Connecting -> "Connecting websocket"
                VisionAgentConnectionState.Ready -> "Streaming to backend"
                VisionAgentConnectionState.Disconnected -> "Disconnected"
                is VisionAgentConnectionState.Error -> "Error"
            },
            style = MaterialTheme.typography.bodySmall,
            color = Color.White,
        )
        uiState.provider?.let {
            Text("Provider: $it", style = MaterialTheme.typography.bodySmall, color = Color.White)
        }
        uiState.callId?.let {
            Text("Call: $it", style = MaterialTheme.typography.bodySmall, color = Color.White)
        }
        uiState.agentSessionId?.let {
            Text("Agent: $it", style = MaterialTheme.typography.bodySmall, color = Color.White)
        }
        Text(
            "Frames ${uiState.videoFrames}  Audio ${uiState.audioChunks}",
            style = MaterialTheme.typography.bodySmall,
            color = Color.White,
        )
        if (uiState.userTranscript.isNotBlank()) {
            Text(
                "You: ${uiState.userTranscript}",
                style = MaterialTheme.typography.bodySmall,
                color = Color.White,
            )
        }
        if (uiState.assistantTranscript.isNotBlank()) {
            Text(
                "AI: ${uiState.assistantTranscript}",
                style = MaterialTheme.typography.bodySmall,
                color = Color.White,
            )
        }
        if (uiState.visionAgentError != null) {
            Text(
                "Agent bootstrap warning: ${uiState.visionAgentError}",
                style = MaterialTheme.typography.bodySmall,
                color = Color.White,
            )
        }
    }
}
