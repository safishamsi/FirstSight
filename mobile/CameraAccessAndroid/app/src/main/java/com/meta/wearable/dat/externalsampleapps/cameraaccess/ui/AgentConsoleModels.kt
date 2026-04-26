package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import com.meta.wearable.dat.externalsampleapps.cameraaccess.settings.SettingsManager
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentMode

enum class ConsoleTab {
    AGENTS,
    GUIDEBOOKS,
    SESSIONS,
}

enum class AgentRuntimeProfile(
    val title: String,
    val summary: String,
) {
    REALTIME(
        title = "Realtime Voice Agent",
        summary = "Python backend handles live speech and first-aid guidance.",
    ),
    PIPELINE(
        title = "VLM + STT + TTS",
        summary = "Fast Whisper pipeline with deterministic first-aid checklist control.",
    ),
    DIRECT_GEMINI(
        title = "Direct Gemini Lab",
        summary = "Android talks directly to Gemini without the Python backend.",
    ),
}

enum class TriggerMode(
    val storageValue: String,
    val label: String,
) {
    PUSH_TO_TALK("push_to_talk", "Push to Talk"),
    CONTINUOUS("continuous", "Continuous"),
    EVENT("event", "Event Triggered");

    companion object {
        fun fromStorage(value: String): TriggerMode =
            entries.firstOrNull { it.storageValue == value } ?: PUSH_TO_TALK
    }
}

data class AgentToolState(
    val label: String,
    val enabled: Boolean,
    val persistentKey: String,
)

data class AgentProfileDraft(
    val name: String,
    val systemPrompt: String,
    val runtimeProfile: AgentRuntimeProfile,
    val guidebookTitle: String,
    val knowledgeSourceLabel: String,
    val backendBaseUrl: String,
    val knowledgeEndpoint: String,
    val userName: String,
    val turnDelayMs: String,
    val geminiModel: String,
    val whisperModelSize: String,
    val ttsEnabled: Boolean,
    val processorEnabled: Boolean,
    val triggerMode: TriggerMode,
    val outputVoiceEnabled: Boolean,
    val outputOverlayEnabled: Boolean,
    val proactiveNotificationsEnabled: Boolean,
    val tools: List<AgentToolState>,
) {
    companion object {
        fun fromSettings(): AgentProfileDraft {
            val runtimeProfile =
                when {
                    SettingsManager.aiBackendMode == VisionAgentMode.DIRECT_GEMINI -> AgentRuntimeProfile.DIRECT_GEMINI
                    SettingsManager.backendSpeechPipeline == "fast_whisper_pipeline" -> AgentRuntimeProfile.PIPELINE
                    else -> AgentRuntimeProfile.REALTIME
                }

            return AgentProfileDraft(
                name = SettingsManager.activeAgentName,
                systemPrompt = SettingsManager.geminiSystemPrompt,
                runtimeProfile = runtimeProfile,
                guidebookTitle = SettingsManager.activeGuidebookTitle,
                knowledgeSourceLabel = SettingsManager.activeKnowledgeSourceLabel,
                backendBaseUrl = SettingsManager.backendBaseUrl,
                knowledgeEndpoint = SettingsManager.visionToolBaseUrl,
                userName = SettingsManager.backendUserName,
                turnDelayMs = SettingsManager.backendTurnDelayMs.toString(),
                geminiModel = SettingsManager.backendGeminiModel,
                whisperModelSize = SettingsManager.backendFastWhisperModelSize,
                ttsEnabled = SettingsManager.backendTtsEnabled,
                processorEnabled = SettingsManager.backendEnablePoseProcessor,
                triggerMode = TriggerMode.fromStorage(SettingsManager.activeTriggerMode),
                outputVoiceEnabled = SettingsManager.activeOutputVoiceEnabled,
                outputOverlayEnabled = SettingsManager.activeOutputOverlayEnabled,
                proactiveNotificationsEnabled = SettingsManager.proactiveNotificationsEnabled,
                tools =
                    listOf(
                        AgentToolState("Visual Checks", SettingsManager.activeToolVisionEnabled, "vision"),
                        AgentToolState("OCR / Label Reading", SettingsManager.activeToolOcrEnabled, "ocr"),
                        AgentToolState("Spatial Search Overlays", SettingsManager.activeToolSpatialEnabled, "spatial"),
                        AgentToolState("First-Aid Playbooks", SettingsManager.activeToolGuidebooksEnabled, "guidebooks"),
                        AgentToolState("External Actions", SettingsManager.activeToolExecuteEnabled, "execute"),
                        AgentToolState("Guide Search", SettingsManager.activeToolKnowledgeEnabled, "knowledge"),
                    ),
            )
        }
    }

    fun saveToSettings() {
        SettingsManager.activeAgentName = name.trim().ifBlank { "First Aid Responder" }
        SettingsManager.geminiSystemPrompt = systemPrompt.trim().ifBlank { SettingsManager.DEFAULT_SYSTEM_PROMPT }
        SettingsManager.activeGuidebookTitle = guidebookTitle.trim().ifBlank { "Stroke FAST Check" }
        SettingsManager.activeKnowledgeSourceLabel = knowledgeSourceLabel.trim().ifBlank { "First Aid Playbooks" }
        SettingsManager.backendBaseUrl = backendBaseUrl.trim()
        SettingsManager.visionToolBaseUrl = knowledgeEndpoint.trim()
        SettingsManager.backendUserName = userName.trim()
        SettingsManager.backendTurnDelayMs = turnDelayMs.trim().toIntOrNull() ?: SettingsManager.backendTurnDelayMs
        SettingsManager.backendGeminiModel = geminiModel.trim().ifBlank { "gemini-3-flash-preview" }
        SettingsManager.backendFastWhisperModelSize = whisperModelSize.trim().ifBlank { "base" }
        SettingsManager.backendTtsEnabled = ttsEnabled
        SettingsManager.backendEnablePoseProcessor = processorEnabled
        SettingsManager.activeTriggerMode = triggerMode.storageValue
        SettingsManager.activeOutputVoiceEnabled = outputVoiceEnabled
        SettingsManager.activeOutputOverlayEnabled = outputOverlayEnabled
        SettingsManager.proactiveNotificationsEnabled = proactiveNotificationsEnabled

        SettingsManager.aiBackendMode =
            when (runtimeProfile) {
                AgentRuntimeProfile.DIRECT_GEMINI -> VisionAgentMode.DIRECT_GEMINI
                AgentRuntimeProfile.REALTIME,
                AgentRuntimeProfile.PIPELINE -> VisionAgentMode.VISION_AGENT_BACKEND
            }
        SettingsManager.backendSpeechPipeline =
            when (runtimeProfile) {
                AgentRuntimeProfile.PIPELINE -> "fast_whisper_pipeline"
                AgentRuntimeProfile.REALTIME,
                AgentRuntimeProfile.DIRECT_GEMINI -> "realtime"
            }

        tools.forEach { tool ->
            when (tool.persistentKey) {
                "vision" -> SettingsManager.activeToolVisionEnabled = tool.enabled
                "ocr" -> SettingsManager.activeToolOcrEnabled = tool.enabled
                "spatial" -> {
                    SettingsManager.activeToolSpatialEnabled = tool.enabled
                    SettingsManager.backendEnablePoseProcessor = tool.enabled && processorEnabled
                }
                "guidebooks" -> SettingsManager.activeToolGuidebooksEnabled = tool.enabled
                "execute" -> SettingsManager.activeToolExecuteEnabled = tool.enabled
                "knowledge" -> SettingsManager.activeToolKnowledgeEnabled = tool.enabled
            }
        }
    }
}

data class AgentLibraryCard(
    val id: String,
    val title: String,
    val guidebookTitle: String,
    val status: String,
    val summary: String,
    val toolCount: Int,
    val runtimeLabel: String,
    val editable: Boolean,
)

fun activeAgentLibraryCard(): AgentLibraryCard {
    val draft = AgentProfileDraft.fromSettings()
    return AgentLibraryCard(
        id = "active",
        title = draft.name.uppercase(),
        guidebookTitle = draft.guidebookTitle,
        status = if (draft.backendBaseUrl.isBlank()) "DRAFT" else "READY",
        summary = draft.runtimeProfile.summary,
        toolCount = draft.tools.count { it.enabled },
        runtimeLabel = draft.runtimeProfile.title,
        editable = true,
    )
}

fun templateAgentCards(): List<AgentLibraryCard> =
    emptyList()

fun applyAgentTemplate(templateId: String) {
    val template = AgentProfileDraft.fromSettings()
    template.saveToSettings()
}
