package com.meta.wearable.dat.externalsampleapps.cameraaccess.guidance

import org.json.JSONObject

data class GuidanceSessionState(
    val isActive: Boolean = false,
    val sessionId: String? = null,
    val task: String = "",
    val stepIndex: Int = 0,
    val stepTitle: String = "",
    val targetQuery: String? = null,
    val instruction: String? = null,
) {
    companion object {
        fun fromJSON(json: JSONObject): GuidanceSessionState =
            GuidanceSessionState(
                isActive = true,
                sessionId = json.optString("sessionId").takeIf { it.isNotBlank() },
                task = json.optString("task", ""),
                stepIndex = json.optInt("stepIndex", 0),
                stepTitle = json.optString("stepTitle", ""),
                targetQuery = json.optString("targetQuery").takeIf { it.isNotBlank() },
                instruction = json.optString("instruction").takeIf { it.isNotBlank() },
            )
    }
}
