package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.meta.wearable.dat.externalsampleapps.cameraaccess.platform.ObjectInfoPanelState

@Composable
fun ObjectInfoPanel(
    state: ObjectInfoPanelState,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    if (!state.visible) return

    Column(
        modifier =
            modifier
                .fillMaxWidth()
                .background(Color(0xE6000000), RoundedCornerShape(16.dp))
                .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = if (state.title.isNotBlank()) state.title else state.label,
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                )
                if (state.usedFor != null) {
                    Text(
                        text = state.usedFor,
                        color = Color(0xFF9FE7FF),
                    )
                }
            }
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = "Dismiss",
                color = Color(0xFF00E5FF),
                modifier = Modifier.clickable(onClick = onDismiss),
            )
        }

        Text(
            text = state.description,
            color = Color.White.copy(alpha = 0.92f),
        )

        if (state.searchResults.isNotEmpty()) {
            Text(
                text = "Related results",
                color = Color.White,
                fontWeight = FontWeight.SemiBold,
            )
            state.searchResults.take(3).forEach { result ->
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        text = result.title,
                        color = Color(0xFF00E5FF),
                        fontWeight = FontWeight.Medium,
                    )
                    Text(
                        text = result.snippet,
                        color = Color.White.copy(alpha = 0.8f),
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}
