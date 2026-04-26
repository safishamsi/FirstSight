package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
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
            .border(1.dp, Color.White.copy(alpha = 0.75f))
            .background(Color.Black.copy(alpha = 0.60f))
            .padding(horizontal = 10.dp, vertical = 8.dp),
        color = Color.White,
        fontFamily = FontFamily.Monospace,
        fontWeight = FontWeight.Bold,
    )
}

@Composable
fun AiModeSwitcher(
    mode: VisionAgentMode,
    onModeSelected: (VisionAgentMode) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        AiModeOptionButton(
            label = "Gemini Lab",
            selected = mode == VisionAgentMode.DIRECT_GEMINI,
            onClick = { onModeSelected(VisionAgentMode.DIRECT_GEMINI) },
        )
        AiModeOptionButton(
            label = "Vision Backend",
            selected = mode == VisionAgentMode.VISION_AGENT_BACKEND,
            onClick = { onModeSelected(VisionAgentMode.VISION_AGENT_BACKEND) },
        )
    }
}

@Composable
private fun AiModeOptionButton(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
) {
    Button(
        onClick = onClick,
        shape = androidx.compose.foundation.shape.RoundedCornerShape(2.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = if (selected) OpsColor.Accent else Color.Black.copy(alpha = 0.55f),
            contentColor = Color.White,
        ),
    ) {
        Text(
            text = label.uppercase(),
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
        )
    }
}
