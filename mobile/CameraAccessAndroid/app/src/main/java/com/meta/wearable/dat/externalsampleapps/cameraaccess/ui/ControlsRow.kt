package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@Composable
fun ControlsRow(
    onStopStream: () -> Unit,
    onCapturePhoto: () -> Unit,
    onToggleAI: () -> Unit,
    isAIActive: Boolean,
    onToggleLive: () -> Unit,
    isLiveActive: Boolean,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .navigationBarsPadding()
            .fillMaxWidth()
            .heightIn(min = 56.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Button(
            onClick = onStopStream,
            modifier = Modifier.weight(1.2f),
            colors = ButtonDefaults.buttonColors(containerColor = OpsColor.Danger, contentColor = Color.White),
            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 12.dp),
            shape = androidx.compose.foundation.shape.RoundedCornerShape(2.dp),
        ) {
            Text(
                text = "END",
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
            )
        }

        Button(
            onClick = onCapturePhoto,
            modifier = Modifier.weight(1f),
            colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = OpsColor.Ink),
            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 12.dp),
            shape = androidx.compose.foundation.shape.RoundedCornerShape(2.dp),
        ) {
            Icon(
                imageVector = Icons.Default.PhotoCamera,
                contentDescription = "Capture photo",
            )
            Text(
                text = "CAPTURE",
                modifier = Modifier.padding(start = 6.dp),
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
            )
        }

        Button(
            onClick = onToggleAI,
            modifier = Modifier.weight(1f),
            colors =
                ButtonDefaults.buttonColors(
                    containerColor = if (isAIActive) OpsColor.Accent else Color.White,
                    contentColor = if (isAIActive) Color.White else OpsColor.Ink,
                ),
            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 12.dp),
            shape = androidx.compose.foundation.shape.RoundedCornerShape(2.dp),
        ) {
            Icon(
                imageVector = Icons.Default.AutoAwesome,
                contentDescription = if (isAIActive) "Stop AI" else "Start AI",
            )
            Text(
                text = if (isAIActive) "AGENT ON" else "AGENT",
                modifier = Modifier.padding(start = 6.dp),
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
            )
        }

        Button(
            onClick = onToggleLive,
            modifier = Modifier.weight(1f),
            colors =
                ButtonDefaults.buttonColors(
                    containerColor = if (isLiveActive) OpsColor.AccentSoft else Color.White,
                    contentColor = OpsColor.Ink,
                ),
            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 12.dp),
            shape = androidx.compose.foundation.shape.RoundedCornerShape(2.dp),
        ) {
            Icon(
                imageVector = Icons.Default.Videocam,
                contentDescription = if (isLiveActive) "Stop live" else "Start live",
            )
            Text(
                text = if (isLiveActive) "LIVE ON" else "LIVE",
                modifier = Modifier.padding(start = 6.dp),
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}
