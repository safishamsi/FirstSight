package com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent

enum class VisionAgentMode(val storageValue: String) {
    DIRECT_GEMINI("direct_gemini"),
    VISION_AGENT_BACKEND("vision_agent_backend");

    companion object {
        fun fromStorage(value: String?): VisionAgentMode {
            return entries.firstOrNull { it.storageValue == value } ?: DIRECT_GEMINI
        }
    }
}
