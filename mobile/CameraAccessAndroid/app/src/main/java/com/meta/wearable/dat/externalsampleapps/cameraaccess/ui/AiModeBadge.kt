package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentMode

fun visionAgentModeLabel(mode: VisionAgentMode): String =
    when (mode) {
        VisionAgentMode.DIRECT_GEMINI -> "AI Mode: Direct Gemini"
        VisionAgentMode.VISION_AGENT_BACKEND -> "AI Mode: Vision Agent Backend"
    }

@Composable
fun AiModeBadge(
    mode: VisionAgentMode,
    modifier: Modifier = Modifier,
) {
    Text(
        text = visionAgentModeLabel(mode),
        modifier = modifier
            .background(
                color = Color.Black.copy(alpha = 0.72f),
                shape = RoundedCornerShape(999.dp),
            )
            .padding(horizontal = 12.dp, vertical = 8.dp),
        color = Color.White,
        style = MaterialTheme.typography.labelLarge,
    )
}
