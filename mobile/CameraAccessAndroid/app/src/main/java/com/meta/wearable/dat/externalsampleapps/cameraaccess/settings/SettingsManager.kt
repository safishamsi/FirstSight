package com.meta.wearable.dat.externalsampleapps.cameraaccess.settings

import android.content.Context
import android.content.SharedPreferences
import com.meta.wearable.dat.externalsampleapps.cameraaccess.Secrets
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentMode

object SettingsManager {
    private const val PREFS_NAME = "visionclaw_settings"

    private lateinit var prefs: SharedPreferences

    fun init(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        migrateLegacyDemoDefaults()
    }

    private fun migrateLegacyDemoDefaults() {
        val editor = prefs.edit()
        var changed = false
        if (prefs.getString("activeAgentName", null) == "Field Guide") {
            editor.putString("activeAgentName", "First Aid Responder")
            changed = true
        }
        if (prefs.getString("activeGuidebookTitle", null) == "Warehouse Safety v1") {
            editor.putString("activeGuidebookTitle", "Stroke FAST Check")
            changed = true
        }
        if (prefs.getString("activeKnowledgeSourceLabel", null) == "Warehouse Ops Index") {
            editor.putString("activeKnowledgeSourceLabel", "First Aid Playbooks")
            changed = true
        }
        if (changed) {
            editor.apply()
        }
    }

    var geminiAPIKey: String
        get() = prefs.getString("geminiAPIKey", null) ?: Secrets.geminiAPIKey
        set(value) = prefs.edit().putString("geminiAPIKey", value).apply()

    var geminiSystemPrompt: String
        get() = prefs.getString("geminiSystemPrompt", null) ?: DEFAULT_SYSTEM_PROMPT
        set(value) = prefs.edit().putString("geminiSystemPrompt", value).apply()

    var aiBackendMode: VisionAgentMode
        get() = VisionAgentMode.fromStorage(prefs.getString("aiBackendMode", null))
        set(value) = prefs.edit().putString("aiBackendMode", value.storageValue).apply()

    var backendBaseUrl: String
        get() = prefs.getString("backendBaseUrl", null) ?: Secrets.pythonBackendBaseUrl
        set(value) = prefs.edit().putString("backendBaseUrl", value).apply()

    var backendUserId: String
        get() = prefs.getString("backendUserId", null) ?: Secrets.pythonBackendUserId
        set(value) = prefs.edit().putString("backendUserId", value).apply()

    var backendUserName: String
        get() = prefs.getString("backendUserName", null) ?: Secrets.pythonBackendUserName
        set(value) = prefs.edit().putString("backendUserName", value).apply()

    var backendSpeechPipeline: String
        get() = prefs.getString("backendSpeechPipeline", "fast_whisper_pipeline") ?: "fast_whisper_pipeline"
        set(value) = prefs.edit().putString("backendSpeechPipeline", value).apply()

    var backendEnablePoseProcessor: Boolean
        get() = prefs.getBoolean("backendEnablePoseProcessor", true)
        set(value) = prefs.edit().putBoolean("backendEnablePoseProcessor", value).apply()

    var backendGeminiModel: String
        get() = prefs.getString("backendGeminiModel", "gemini-3-flash-preview") ?: "gemini-3-flash-preview"
        set(value) = prefs.edit().putString("backendGeminiModel", value).apply()

    var backendFastWhisperModelSize: String
        get() = prefs.getString("backendFastWhisperModelSize", "base") ?: "base"
        set(value) = prefs.edit().putString("backendFastWhisperModelSize", value).apply()

    var backendFastWhisperDevice: String
        get() = prefs.getString("backendFastWhisperDevice", "cpu") ?: "cpu"
        set(value) = prefs.edit().putString("backendFastWhisperDevice", value).apply()

    var backendTurnDelayMs: Int
        get() = prefs.getInt("backendTurnDelayMs", 1200)
        set(value) = prefs.edit().putInt("backendTurnDelayMs", value).apply()

    var backendTtsEnabled: Boolean
        get() = prefs.getBoolean("backendTtsEnabled", true)
        set(value) = prefs.edit().putBoolean("backendTtsEnabled", value).apply()

    var openClawHost: String
        get() = prefs.getString("openClawHost", null) ?: Secrets.openClawHost
        set(value) = prefs.edit().putString("openClawHost", value).apply()

    var openClawPort: Int
        get() {
            val stored = prefs.getInt("openClawPort", 0)
            return if (stored != 0) stored else Secrets.openClawPort
        }
        set(value) = prefs.edit().putInt("openClawPort", value).apply()

    var openClawHookToken: String
        get() = prefs.getString("openClawHookToken", null) ?: Secrets.openClawHookToken
        set(value) = prefs.edit().putString("openClawHookToken", value).apply()

    var openClawGatewayToken: String
        get() = prefs.getString("openClawGatewayToken", null) ?: Secrets.openClawGatewayToken
        set(value) = prefs.edit().putString("openClawGatewayToken", value).apply()

    var webrtcSignalingURL: String
        get() = prefs.getString("webrtcSignalingURL", null) ?: Secrets.webrtcSignalingURL
        set(value) = prefs.edit().putString("webrtcSignalingURL", value).apply()

    var visionToolBaseUrl: String
        get() = prefs.getString("visionToolBaseUrl", null) ?: "http://127.0.0.1:8765"
        set(value) = prefs.edit().putString("visionToolBaseUrl", value).apply()

    var visionToolAuthToken: String
        get() = prefs.getString("visionToolAuthToken", "") ?: ""
        set(value) = prefs.edit().putString("visionToolAuthToken", value).apply()

    var activeAgentName: String
        get() = prefs.getString("activeAgentName", "First Aid Responder") ?: "First Aid Responder"
        set(value) = prefs.edit().putString("activeAgentName", value).apply()

    var activeGuidebookTitle: String
        get() = prefs.getString("activeGuidebookTitle", "Stroke FAST Check") ?: "Stroke FAST Check"
        set(value) = prefs.edit().putString("activeGuidebookTitle", value).apply()

    var activeKnowledgeSourceLabel: String
        get() = prefs.getString("activeKnowledgeSourceLabel", "First Aid Playbooks") ?: "First Aid Playbooks"
        set(value) = prefs.edit().putString("activeKnowledgeSourceLabel", value).apply()

    var activeTriggerMode: String
        get() = prefs.getString("activeTriggerMode", "push_to_talk") ?: "push_to_talk"
        set(value) = prefs.edit().putString("activeTriggerMode", value).apply()

    var activeOutputVoiceEnabled: Boolean
        get() = prefs.getBoolean("activeOutputVoiceEnabled", true)
        set(value) = prefs.edit().putBoolean("activeOutputVoiceEnabled", value).apply()

    var activeOutputOverlayEnabled: Boolean
        get() = prefs.getBoolean("activeOutputOverlayEnabled", true)
        set(value) = prefs.edit().putBoolean("activeOutputOverlayEnabled", value).apply()

    var activeToolVisionEnabled: Boolean
        get() = prefs.getBoolean("activeToolVisionEnabled", true)
        set(value) = prefs.edit().putBoolean("activeToolVisionEnabled", value).apply()

    var activeToolOcrEnabled: Boolean
        get() = prefs.getBoolean("activeToolOcrEnabled", true)
        set(value) = prefs.edit().putBoolean("activeToolOcrEnabled", value).apply()

    var activeToolSpatialEnabled: Boolean
        get() = prefs.getBoolean("activeToolSpatialEnabled", true)
        set(value) = prefs.edit().putBoolean("activeToolSpatialEnabled", value).apply()

    var activeToolGuidebooksEnabled: Boolean
        get() = prefs.getBoolean("activeToolGuidebooksEnabled", true)
        set(value) = prefs.edit().putBoolean("activeToolGuidebooksEnabled", value).apply()

    var activeToolExecuteEnabled: Boolean
        get() = prefs.getBoolean("activeToolExecuteEnabled", true)
        set(value) = prefs.edit().putBoolean("activeToolExecuteEnabled", value).apply()

    var activeToolKnowledgeEnabled: Boolean
        get() = prefs.getBoolean("activeToolKnowledgeEnabled", true)
        set(value) = prefs.edit().putBoolean("activeToolKnowledgeEnabled", value).apply()

    var videoStreamingEnabled: Boolean
        get() = prefs.getBoolean("videoStreamingEnabled", true)
        set(value) = prefs.edit().putBoolean("videoStreamingEnabled", value).apply()

    var proactiveNotificationsEnabled: Boolean
        get() = prefs.getBoolean("proactiveNotificationsEnabled", false)
        set(value) = prefs.edit().putBoolean("proactiveNotificationsEnabled", value).apply()

    fun resetAll() {
        prefs.edit().clear().apply()
    }

    const val DEFAULT_SYSTEM_PROMPT = """You are a first-aid assistant for someone wearing Meta Ray-Ban smart glasses. You can see through their camera and hold a short live conversation. Keep responses calm, direct, and procedural.

Prefer:
- one concrete next action
- visible evidence from the camera
- the active first-aid checklist when one is loaded

Do:
- help the wearer load the right first-aid guide
- guide them through the current checklist step
- use spatial grounding to look for objects like an AED, first-aid kit, phone, or a clearer airway view
- ask for one specific camera adjustment if the scene is unclear

Do not:
- claim certainty where the scene is unclear
- diagnose beyond the evidence
- pretend to call emergency services or act in the real world on the user's behalf

When a first-aid playbook is active:
- stay anchored on the current step
- keep answers short unless the wearer asks for more detail
- summarize tool results plainly

When no playbook is active:
- help the wearer choose the most relevant first-aid guide
- ask a short clarifying question only if needed"""
}
