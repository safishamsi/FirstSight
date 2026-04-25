package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import android.util.Log
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.foundation.layout.Row
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentMode
import com.meta.wearable.dat.externalsampleapps.cameraaccess.settings.SettingsManager

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val tag = "SettingsScreen"
    var geminiAPIKey by remember { mutableStateOf(SettingsManager.geminiAPIKey) }
    var systemPrompt by remember { mutableStateOf(SettingsManager.geminiSystemPrompt) }
    var aiBackendMode by remember { mutableStateOf(SettingsManager.aiBackendMode) }
    var backendBaseUrl by remember { mutableStateOf(SettingsManager.backendBaseUrl) }
    var backendUserId by remember { mutableStateOf(SettingsManager.backendUserId) }
    var backendUserName by remember { mutableStateOf(SettingsManager.backendUserName) }
    var openClawHost by remember { mutableStateOf(SettingsManager.openClawHost) }
    var openClawPort by remember { mutableStateOf(SettingsManager.openClawPort.toString()) }
    var openClawHookToken by remember { mutableStateOf(SettingsManager.openClawHookToken) }
    var openClawGatewayToken by remember { mutableStateOf(SettingsManager.openClawGatewayToken) }
    var webrtcSignalingURL by remember { mutableStateOf(SettingsManager.webrtcSignalingURL) }
    var visionToolBaseUrl by remember { mutableStateOf(SettingsManager.visionToolBaseUrl) }
    var visionToolAuthToken by remember { mutableStateOf(SettingsManager.visionToolAuthToken) }
    var videoStreamingEnabled by remember { mutableStateOf(SettingsManager.videoStreamingEnabled) }
    var proactiveNotificationsEnabled by remember { mutableStateOf(SettingsManager.proactiveNotificationsEnabled) }
    var showResetDialog by remember { mutableStateOf(false) }

    fun save() {
        SettingsManager.geminiAPIKey = geminiAPIKey.trim()
        SettingsManager.geminiSystemPrompt = systemPrompt.trim()
        SettingsManager.aiBackendMode = aiBackendMode
        SettingsManager.backendBaseUrl = backendBaseUrl.trim()
        SettingsManager.backendUserId = backendUserId.trim()
        SettingsManager.backendUserName = backendUserName.trim()
        SettingsManager.openClawHost = openClawHost.trim()
        openClawPort.trim().toIntOrNull()?.let { SettingsManager.openClawPort = it }
        SettingsManager.openClawHookToken = openClawHookToken.trim()
        SettingsManager.openClawGatewayToken = openClawGatewayToken.trim()
        SettingsManager.webrtcSignalingURL = webrtcSignalingURL.trim()
        SettingsManager.visionToolBaseUrl = visionToolBaseUrl.trim()
        SettingsManager.visionToolAuthToken = visionToolAuthToken.trim()
        SettingsManager.videoStreamingEnabled = videoStreamingEnabled
        SettingsManager.proactiveNotificationsEnabled = proactiveNotificationsEnabled
        Log.d(
            tag,
            "Saved OpenClaw settings: host='${SettingsManager.openClawHost}' port=${SettingsManager.openClawPort} hookTokenPresent=${SettingsManager.openClawHookToken.isNotBlank()} gatewayTokenPresent=${SettingsManager.openClawGatewayToken.isNotBlank()}",
        )
    }

    fun reload() {
        geminiAPIKey = SettingsManager.geminiAPIKey
        systemPrompt = SettingsManager.geminiSystemPrompt
        aiBackendMode = SettingsManager.aiBackendMode
        backendBaseUrl = SettingsManager.backendBaseUrl
        backendUserId = SettingsManager.backendUserId
        backendUserName = SettingsManager.backendUserName
        openClawHost = SettingsManager.openClawHost
        openClawPort = SettingsManager.openClawPort.toString()
        openClawHookToken = SettingsManager.openClawHookToken
        openClawGatewayToken = SettingsManager.openClawGatewayToken
        webrtcSignalingURL = SettingsManager.webrtcSignalingURL
        visionToolBaseUrl = SettingsManager.visionToolBaseUrl
        visionToolAuthToken = SettingsManager.visionToolAuthToken
        videoStreamingEnabled = SettingsManager.videoStreamingEnabled
        proactiveNotificationsEnabled = SettingsManager.proactiveNotificationsEnabled
        Log.d(
            tag,
            "Reloaded OpenClaw settings: host='${SettingsManager.openClawHost}' port=${SettingsManager.openClawPort} hookTokenPresent=${SettingsManager.openClawHookToken.isNotBlank()} gatewayTokenPresent=${SettingsManager.openClawGatewayToken.isNotBlank()}",
        )
    }

    Column(modifier = modifier.fillMaxSize()) {
        TopAppBar(
            title = { Text("Settings") },
            navigationIcon = {
                IconButton(onClick = {
                    save()
                    onBack()
                }) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                }
            },
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp)
                .navigationBarsPadding(),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            // Gemini section
            SectionHeader("AI Session Mode")
            Text(
                "Choose whether the app talks directly to Gemini or routes media through the Python backend.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                ModeButton(
                    label = "Direct Gemini",
                    selected = aiBackendMode == VisionAgentMode.DIRECT_GEMINI,
                    onClick = { aiBackendMode = VisionAgentMode.DIRECT_GEMINI },
                    modifier = Modifier.weight(1f),
                )
                ModeButton(
                    label = "Vision Agent Backend",
                    selected = aiBackendMode == VisionAgentMode.VISION_AGENT_BACKEND,
                    onClick = { aiBackendMode = VisionAgentMode.VISION_AGENT_BACKEND },
                    modifier = Modifier.weight(1f),
                )
            }

            SectionHeader("Gemini API")
            MonoTextField(
                value = geminiAPIKey,
                onValueChange = { geminiAPIKey = it },
                label = "API Key",
                placeholder = "Enter Gemini API key",
            )

            SectionHeader("Vision Agent Backend")
            MonoTextField(
                value = backendBaseUrl,
                onValueChange = { backendBaseUrl = it },
                label = "Base URL",
                placeholder = "http://your-mac.local:8000",
                keyboardType = KeyboardType.Uri,
            )
            MonoTextField(
                value = backendUserId,
                onValueChange = { backendUserId = it },
                label = "User ID",
                placeholder = "android-demo-user",
            )
            MonoTextField(
                value = backendUserName,
                onValueChange = { backendUserName = it },
                label = "Display Name",
                placeholder = "DroopDetection Demo",
            )

            SectionHeader("System Prompt")
            OutlinedTextField(
                value = systemPrompt,
                onValueChange = { systemPrompt = it },
                label = { Text("System prompt") },
                modifier = Modifier.fillMaxWidth().height(200.dp),
                textStyle = MaterialTheme.typography.bodyMedium.copy(fontFamily = FontFamily.Monospace),
            )

            // OpenClaw section
            SectionHeader("OpenClaw")
            MonoTextField(
                value = openClawHost,
                onValueChange = { openClawHost = it },
                label = "Host",
                placeholder = "http://your-mac.local",
                keyboardType = KeyboardType.Uri,
            )
            MonoTextField(
                value = openClawPort,
                onValueChange = { openClawPort = it },
                label = "Port",
                placeholder = "18789",
                keyboardType = KeyboardType.Number,
            )
            MonoTextField(
                value = openClawHookToken,
                onValueChange = { openClawHookToken = it },
                label = "Hook Token",
                placeholder = "Hook token",
            )
            MonoTextField(
                value = openClawGatewayToken,
                onValueChange = { openClawGatewayToken = it },
                label = "Gateway Token",
                placeholder = "Gateway auth token",
            )

            // WebRTC section
            SectionHeader("WebRTC")
            MonoTextField(
                value = webrtcSignalingURL,
                onValueChange = { webrtcSignalingURL = it },
                label = "Signaling URL",
                placeholder = "wss://your-server.example.com",
                keyboardType = KeyboardType.Uri,
            )

            SectionHeader("Vision Tool")
            MonoTextField(
                value = visionToolBaseUrl,
                onValueChange = { visionToolBaseUrl = it },
                label = "Service URL",
                placeholder = "http://your-mac.local:8765",
                keyboardType = KeyboardType.Uri,
            )
            MonoTextField(
                value = visionToolAuthToken,
                onValueChange = { visionToolAuthToken = it },
                label = "Auth Token",
                placeholder = "Optional bearer token",
            )

            // Video
            SectionHeader("Video")
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
            ) {
                Column {
                    Text("Video Streaming", style = MaterialTheme.typography.bodyLarge)
                    Text(
                        "Disable to save battery. Audio remains active.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = videoStreamingEnabled,
                    onCheckedChange = { videoStreamingEnabled = it },
                )
            }

            // Notifications
            SectionHeader("Notifications")
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
            ) {
                Column {
                    Text("Proactive Notifications", style = MaterialTheme.typography.bodyLarge)
                    Text(
                        "Off by default for the demo to avoid OpenClaw reconnect noise.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = proactiveNotificationsEnabled,
                    onCheckedChange = { proactiveNotificationsEnabled = it },
                )
            }

            // Reset
            TextButton(onClick = { showResetDialog = true }) {
                Text("Reset to Defaults", color = Color.Red)
            }

            Spacer(modifier = Modifier.height(32.dp))
        }
    }

    if (showResetDialog) {
        AlertDialog(
            onDismissRequest = { showResetDialog = false },
            title = { Text("Reset Settings") },
            text = { Text("This will reset all settings to the values built into the app.") },
            confirmButton = {
                TextButton(onClick = {
                    SettingsManager.resetAll()
                    reload()
                    showResetDialog = false
                }) {
                    Text("Reset", color = Color.Red)
                }
            },
            dismissButton = {
                TextButton(onClick = { showResetDialog = false }) {
                    Text("Cancel")
                }
            },
        )
    }
}

@Composable
private fun SectionHeader(title: String) {
    Text(
        text = title,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.primary,
    )
}

@Composable
private fun MonoTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    placeholder: String,
    keyboardType: KeyboardType = KeyboardType.Text,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        placeholder = { Text(placeholder) },
        modifier = Modifier.fillMaxWidth(),
        textStyle = MaterialTheme.typography.bodyMedium.copy(fontFamily = FontFamily.Monospace),
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType),
    )
}

@Composable
private fun ModeButton(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Button(
        onClick = onClick,
        modifier = modifier,
        colors = ButtonDefaults.buttonColors(
            containerColor = if (selected) AppColor.DeepBlue else MaterialTheme.colorScheme.surfaceVariant,
            contentColor = if (selected) Color.White else MaterialTheme.colorScheme.onSurface,
        ),
    ) {
        Text(label)
    }
}
