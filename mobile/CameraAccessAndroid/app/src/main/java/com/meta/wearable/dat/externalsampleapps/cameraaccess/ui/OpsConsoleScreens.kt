package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.LinkOff
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.meta.wearable.dat.externalsampleapps.cameraaccess.settings.SettingsManager
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentGuideClient
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentGuideDetail
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentGuideSummary
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun VisionOpsConsole(
    isRegistered: Boolean,
    hasActiveDevice: Boolean,
    primaryActionLabel: String,
    primaryActionEnabled: Boolean,
    onPrimaryAction: () -> Unit,
    onPhoneMode: () -> Unit,
    onShowSettings: () -> Unit,
    onDisconnect: (() -> Unit)?,
    modifier: Modifier = Modifier,
) {
    var selectedTab by rememberSaveable { mutableStateOf(ConsoleTab.AGENTS) }
    var refreshCounter by rememberSaveable { mutableIntStateOf(0) }
    val activeCard = remember(refreshCounter) { activeAgentLibraryCard() }

    OpsScreen(modifier = modifier) {
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .padding(top = 10.dp),
        ) {
            OpsTopBar(
                title = "VISION OPS",
                subtitle = "Active device: ${if (hasActiveDevice) "Ray-Ban Meta connected" else "Waiting for device"}",
                trailing = {
                    OpsIconAction(onClick = onShowSettings) {
                        Icon(
                            imageVector = Icons.Default.Settings,
                            contentDescription = "Settings",
                            tint = OpsColor.Ink,
                        )
                    }
                    if (onDisconnect != null && isRegistered) {
                        OpsIconAction(onClick = onDisconnect) {
                            Icon(
                                imageVector = Icons.Default.LinkOff,
                                contentDescription = "Disconnect",
                                tint = OpsColor.Danger,
                            )
                        }
                    }
                },
            )

            Column(
                modifier =
                    Modifier
                        .weight(1f)
                        .padding(horizontal = 16.dp)
                        .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                when (selectedTab) {
                    ConsoleTab.AGENTS ->
                        AgentsTab(
                            isRegistered = isRegistered,
                            hasActiveDevice = hasActiveDevice,
                            activeCard = activeCard,
                            primaryActionLabel = primaryActionLabel,
                            primaryActionEnabled = primaryActionEnabled,
                            onPrimaryAction = onPrimaryAction,
                            onEditAgent = onShowSettings,
                            onApplyTemplate = {
                                applyAgentTemplate(it)
                                refreshCounter += 1
                            },
                        )
                    ConsoleTab.GUIDEBOOKS ->
                        GuidebooksTab(
                            onGuideSelected = { guide ->
                                SettingsManager.activeGuidebookTitle = guide.title
                                refreshCounter += 1
                            },
                            onOpenSettings = onShowSettings,
                        )
                    ConsoleTab.SESSIONS ->
                        SessionsTab(
                            isRegistered = isRegistered,
                            hasActiveDevice = hasActiveDevice,
                        )
                }
            }

            OpsPanel(
                modifier =
                    Modifier
                        .padding(horizontal = 16.dp, vertical = 12.dp)
                        .navigationBarsPadding(),
            ) {
                OpsSectionHeader("Launch Surface")
                OpsBodyText(
                    text =
                        if (isRegistered) {
                            "The augmented live stream remains the main canvas. Session details and logs open inside the stream view."
                        } else {
                            "Connect first to unlock live glasses streaming. Phone mode stays available for UI and runtime checks."
                        },
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OpsPrimaryButton(
                        label = primaryActionLabel,
                        onClick = onPrimaryAction,
                        enabled = primaryActionEnabled,
                        modifier = Modifier.weight(1f),
                    )
                    OpsSecondaryButton(
                        label = "Start on Phone",
                        onClick = onPhoneMode,
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            OpsBottomNav(
                selected = selectedTab,
                onSelected = { selectedTab = it },
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            )
        }
    }
}

@Composable
private fun AgentsTab(
    isRegistered: Boolean,
    hasActiveDevice: Boolean,
    activeCard: AgentLibraryCard,
    primaryActionLabel: String,
    primaryActionEnabled: Boolean,
    onPrimaryAction: () -> Unit,
    onEditAgent: () -> Unit,
    onApplyTemplate: (String) -> Unit,
) {
    OpsPanel {
        OpsSectionHeader("Responder Profile")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OpsTag(
                label = if (isRegistered) "System Online" else "Registration Required",
                background = if (isRegistered) OpsColor.Success else OpsColor.Warning,
            )
            OpsTag(
                label = if (hasActiveDevice) "Device Connected" else "No Active Device",
                background = if (hasActiveDevice) OpsColor.AccentSoft else Color(0xFFEAEAEA),
            )
        }
        OpsBodyText(
            text = "This app now uses one active first-aid responder profile. Adjust its runtime, prompts, and tool toggles in settings.",
        )
    }

    AgentCard(
        card = activeCard,
        primaryLabel = primaryActionLabel,
        primaryEnabled = primaryActionEnabled,
        onPrimary = onPrimaryAction,
        secondaryLabel = "Edit",
        onSecondary = onEditAgent,
        secondaryIcon = Icons.Default.Edit,
    )

    OpsPanel {
        OpsSectionHeader("Playbook Runtime")
        OpsBodyText(
            text = "Use the config screen to tune one first-aid agent, then switch procedures from the guide library inside the live session.",
        )
    }
}

@Composable
private fun AgentCard(
    card: AgentLibraryCard,
    primaryLabel: String,
    primaryEnabled: Boolean,
    onPrimary: () -> Unit,
    secondaryLabel: String,
    onSecondary: () -> Unit,
    secondaryIcon: androidx.compose.ui.graphics.vector.ImageVector,
) {
    OpsPanel {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = card.title,
                    color = OpsColor.Ink,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    fontSize = 22.sp,
                )
                Text(
                    text = card.summary,
                    color = OpsColor.MutedInk,
                    fontSize = 12.sp,
                    lineHeight = 16.sp,
                )
            }
            OpsTag(
                label = card.status,
                background =
                    when (card.status) {
                        "READY" -> OpsColor.Success
                        "DRAFT" -> Color(0xFFEAEAEA)
                        else -> OpsColor.Warning
                    },
            )
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OpsTag(label = card.guidebookTitle, background = Color(0xFFEDEDED))
            OpsTag(label = "${card.toolCount} tools", background = Color(0xFFEDEDED))
        }
        OpsBodyText(text = "Runtime: ${card.runtimeLabel}")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OpsPrimaryButton(
                label = primaryLabel,
                onClick = onPrimary,
                modifier = Modifier.weight(1f),
                enabled = primaryEnabled,
            )
            Button(
                onClick = onSecondary,
                modifier = Modifier.weight(1f),
                shape = androidx.compose.foundation.shape.RoundedCornerShape(2.dp),
                border = BorderStroke(1.dp, OpsColor.Border),
                colors =
                    ButtonDefaults.buttonColors(
                        containerColor = Color.White,
                        contentColor = OpsColor.Ink,
                    ),
            ) {
                Icon(
                    imageVector = secondaryIcon,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp),
                )
                Spacer(modifier = Modifier.size(6.dp))
                Text(
                    text = secondaryLabel.uppercase(),
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    fontSize = 11.sp,
                )
            }
        }
    }
}

@Composable
private fun GuidebooksTab(
    onGuideSelected: (VisionAgentGuideSummary) -> Unit,
    onOpenSettings: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val client = remember { VisionAgentGuideClient() }
    var query by rememberSaveable { mutableStateOf("") }
    var guides by remember { mutableStateOf<List<VisionAgentGuideSummary>>(emptyList()) }
    var selectedGuide by remember { mutableStateOf<VisionAgentGuideDetail?>(null) }
    var isLoading by remember { mutableStateOf(false) }

    suspend fun loadGuides(currentQuery: String) {
        isLoading = true
        val normalized = currentQuery.trim()
        guides =
            withContext(Dispatchers.IO) {
                if (normalized.length >= 2) {
                    client.searchGuides(normalized)
                } else {
                    client.listGuides()
                }
            }
        selectedGuide =
            guides.firstOrNull()?.let { first ->
                withContext(Dispatchers.IO) { client.fetchGuide(first.id) }
            }
        isLoading = false
    }

    LaunchedEffect(Unit) {
        loadGuides("")
    }

    OpsPanel {
        OpsSectionHeader("First-Aid Guides")
        OpsBodyText(text = "Pick a first-aid playbook here, then load it into the live backend session when you are ready.")
        OpsTextField(
            value = query,
            onValueChange = { query = it },
            label = "Search",
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OpsSecondaryButton(
                label = "Filter",
                onClick = { scope.launch { loadGuides(query) } },
                modifier = Modifier.weight(1f),
            )
            OpsSecondaryButton(
                label = "Edit Agent",
                onClick = onOpenSettings,
                modifier = Modifier.weight(1f),
            )
        }
    }

    if (isLoading) {
        OpsPanel {
            OpsSectionHeader("Loading")
            OpsBodyText(text = "Fetching guidebook library from the backend.")
        }
    }

    guides.forEach { guide ->
        OpsPanel(
            modifier = Modifier.clickable {
                scope.launch {
                    selectedGuide = withContext(Dispatchers.IO) { client.fetchGuide(guide.id) }
                }
            },
        ) {
            Text(
                text = guide.title.uppercase(),
                color = OpsColor.Ink,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                fontSize = 16.sp,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                guide.incidentType?.takeIf { it.isNotBlank() }?.let {
                    OpsTag(label = it, background = OpsColor.Warning)
                }
                OpsTag(label = guide.severity, background = Color(0xFFEDEDED))
            }
            Text(
                text = guide.summary,
                color = OpsColor.MutedInk,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
                fontSize = 12.sp,
                lineHeight = 16.sp,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OpsSecondaryButton(
                    label = "Preview",
                    onClick = {
                        scope.launch {
                            selectedGuide = withContext(Dispatchers.IO) { client.fetchGuide(guide.id) }
                        }
                    },
                    modifier = Modifier.weight(1f),
                )
                OpsPrimaryButton(
                    label = "Attach",
                    onClick = { onGuideSelected(guide) },
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }

    selectedGuide?.let { detail ->
        OpsPanel {
            OpsSectionHeader("Selected Guide", trailing = {
                OpsTag(label = "${detail.checklistTemplate.size} steps", background = OpsColor.AccentSoft)
            })
            Text(
                text = detail.title.uppercase(),
                color = OpsColor.Ink,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                fontSize = 18.sp,
            )
            OpsBodyText(text = detail.summary, muted = false)
            detail.checklistTemplate.take(4).forEachIndexed { index, step ->
                OpsBodyText(text = "${index + 1}. $step")
            }
        }
    }
}

@Composable
private fun SessionsTab(
    isRegistered: Boolean,
    hasActiveDevice: Boolean,
) {
    OpsPanel {
        OpsSectionHeader("Sessions")
        OpsBodyText(
            text = "Live sessions now prioritize the augmented video surface. Transcript history, checklist state, and runtime telemetry move into the stream log drawer instead of replacing the video feed.",
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OpsTag(
                label = if (isRegistered) "System Incident Log" else "Awaiting Registration",
                background = if (isRegistered) OpsColor.AccentSoft else OpsColor.Warning,
            )
            OpsTag(
                label = if (hasActiveDevice) "Read / Write" else "Read / Only",
                background = Color(0xFFEDEDED),
            )
        }
    }

    Card(
        border = BorderStroke(1.dp, OpsColor.Border),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = "No session logs captured yet.",
                color = OpsColor.Ink,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
            )
            OpsBodyText(
                text = "Start a live stream and open the session drawer to inspect transcripts, guidebook progress, session IDs, and backend status without giving up the camera surface.",
            )
            OpsTag(label = "Live stream owns the log view", background = Color(0xFFEDEDED))
        }
    }
    Spacer(modifier = Modifier.height(12.dp))
}
