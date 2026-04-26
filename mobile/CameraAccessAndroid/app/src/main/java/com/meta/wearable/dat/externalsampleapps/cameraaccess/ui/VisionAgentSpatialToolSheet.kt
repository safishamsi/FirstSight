package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentSpatialToolMode

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VisionAgentSpatialToolSheet(
    isPending: Boolean,
    onRunTool: (query: String, mode: VisionAgentSpatialToolMode) -> Unit,
    onClear: () -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    var query by remember { mutableStateOf("") }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        Column(
            modifier =
                modifier
                    .fillMaxWidth()
                    .fillMaxHeight(0.75f)
                    .padding(horizontal = 20.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = "Spatial Tools",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = "Run a one-shot visual tool on the latest frame and publish the result as a backend overlay.",
                style = MaterialTheme.typography.bodyMedium,
                color = Color.White.copy(alpha = 0.8f),
            )
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                label = { Text("Object or target") },
                placeholder = { Text("fork, AED, face, left hand") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedButton(
                    enabled = !isPending,
                    onClick = { onRunTool(query, VisionAgentSpatialToolMode.Box) },
                ) {
                    Text("Box")
                }
                OutlinedButton(
                    enabled = !isPending,
                    onClick = { onRunTool(query, VisionAgentSpatialToolMode.Point) },
                ) {
                    Text("Point")
                }
                OutlinedButton(
                    enabled = !isPending,
                    onClick = { onRunTool(query, VisionAgentSpatialToolMode.Outline) },
                ) {
                    Text("Outline")
                }
                OutlinedButton(
                    enabled = !isPending,
                    onClick = onClear,
                ) {
                    Text("Clear")
                }
            }
            Text(
                text = "Example: type \"fork\" and tap Box to force a bounding-box search on the current frame.",
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.72f),
            )
            if (isPending) {
                CircularProgressIndicator()
            }
        }
    }
}
