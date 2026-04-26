package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentGuideClient
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentGuideDetail
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentGuideSummary
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GuideBrowserSheet(
    activeSessionId: String?,
    onLoadGuideIntoSession: (protocolId: String, matchedQuery: String?, onComplete: (Boolean, String?) -> Unit) -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val scope = rememberCoroutineScope()
    val guideClient = remember { VisionAgentGuideClient() }
    var query by remember { mutableStateOf("") }
    var isLoading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var guides by remember { mutableStateOf<List<VisionAgentGuideSummary>>(emptyList()) }
    var selectedGuide by remember { mutableStateOf<VisionAgentGuideDetail?>(null) }
    var isLoadIntoSessionPending by remember { mutableStateOf(false) }

    suspend fun loadGuides(currentQuery: String) {
        isLoading = true
        errorMessage = null
        val normalizedQuery = currentQuery.trim()
        val nextGuides =
            withContext(Dispatchers.IO) {
                if (normalizedQuery.length >= 2) {
                    guideClient.searchGuides(normalizedQuery)
                } else {
                    guideClient.listGuides()
                }
            }
        guides = nextGuides
        isLoading = false
        if (nextGuides.isEmpty()) {
            selectedGuide = null
            errorMessage = if (normalizedQuery.length >= 2) "No guides matched that search." else "No guides available."
        } else if (selectedGuide == null || nextGuides.none { it.id == selectedGuide?.id }) {
            selectedGuide =
                withContext(Dispatchers.IO) {
                    guideClient.fetchGuide(nextGuides.first().id)
                }
        }
    }

    LaunchedEffect(Unit) {
        loadGuides("")
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        Column(
            modifier =
                modifier
                    .fillMaxWidth()
                    .fillMaxHeight(0.92f)
                    .padding(horizontal = 20.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = "Guide Library",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = "Search the first-aid playbooks and read the active protocol guidance on device.",
                style = MaterialTheme.typography.bodyMedium,
                color = Color.White.copy(alpha = 0.8f),
            )

            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                label = { Text("Search guides") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = {
                        scope.launch {
                            loadGuides(query)
                        }
                    },
                ) {
                    Text("Search")
                }
                TextButton(
                    onClick = {
                        query = ""
                        scope.launch {
                            loadGuides("")
                        }
                    },
                ) {
                    Text("Show all")
                }
            }

            if (isLoading) {
                CircularProgressIndicator()
            }

            errorMessage?.let { message ->
                Text(
                    text = message,
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White.copy(alpha = 0.7f),
                )
            }

            Text(
                text = "Guides",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            LazyColumn(
                modifier = Modifier.weight(1f, fill = false),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(guides, key = { it.id }) { guide ->
                    GuideSummaryCard(
                        guide = guide,
                        selected = selectedGuide?.id == guide.id,
                        onClick = {
                            scope.launch {
                                selectedGuide =
                                    withContext(Dispatchers.IO) {
                                        guideClient.fetchGuide(guide.id)
                                    }
                            }
                        },
                    )
                }
            }

            selectedGuide?.let { detail ->
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = detail.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = detail.summary,
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White.copy(alpha = 0.8f),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(
                        enabled = activeSessionId != null && !isLoadIntoSessionPending,
                        onClick = {
                            isLoadIntoSessionPending = true
                            onLoadGuideIntoSession(detail.id, query.trim().ifBlank { null }) { success, message ->
                                isLoadIntoSessionPending = false
                                errorMessage = message
                                if (success) {
                                    scope.launch {
                                        sheetState.hide()
                                        onDismiss()
                                    }
                                }
                            }
                        },
                    ) {
                        Text(
                            if (isLoadIntoSessionPending) {
                                "Loading..."
                            } else if (activeSessionId == null) {
                                "Start session first"
                            } else {
                                "Load into session"
                            },
                        )
                    }
                }
                GuideManualCard(detail = detail)
            }
        }
    }
}

@Composable
private fun GuideSummaryCard(
    guide: VisionAgentGuideSummary,
    selected: Boolean,
    onClick: () -> Unit,
) {
    val borderColor = if (selected) Color.White else Color.White.copy(alpha = 0.18f)
    Card(
        modifier =
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick),
        border = androidx.compose.foundation.BorderStroke(1.dp, borderColor),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = guide.title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = guide.summary,
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.78f),
            )
            val tagText =
                listOfNotNull(guide.incidentType?.takeIf { it.isNotBlank() }, guide.severity.uppercase())
                    .joinToString(" • ")
            if (tagText.isNotBlank()) {
                Text(
                    text = tagText,
                    style = MaterialTheme.typography.labelSmall,
                    color = Color.White.copy(alpha = 0.62f),
                )
            }
        }
    }
}

@Composable
private fun GuideManualCard(detail: VisionAgentGuideDetail) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color.White.copy(alpha = 0.18f)),
    ) {
        Column(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .heightIn(max = 280.dp)
                    .verticalScroll(rememberScrollState())
                    .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = detail.manualMarkdown,
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.84f),
            )
            if (detail.checklistTemplate.isNotEmpty()) {
                Text(
                    text = "Checklist preview",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold,
                )
                detail.checklistTemplate.forEachIndexed { index, step ->
                    Text(
                        text = "${index + 1}. $step",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.White.copy(alpha = 0.84f),
                    )
                }
            }
        }
    }
}
