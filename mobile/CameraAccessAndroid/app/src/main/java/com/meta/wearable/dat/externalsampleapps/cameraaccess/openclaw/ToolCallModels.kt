package com.meta.wearable.dat.externalsampleapps.cameraaccess.openclaw

import org.json.JSONArray
import org.json.JSONObject

// Gemini Tool Call (parsed from server JSON)

data class GeminiFunctionCall(
    val id: String,
    val name: String,
    val args: Map<String, Any?>
)

data class GeminiToolCall(
    val functionCalls: List<GeminiFunctionCall>
) {
    companion object {
        fun fromJSON(json: JSONObject): GeminiToolCall? {
            val toolCall = json.optJSONObject("toolCall") ?: return null
            val calls = toolCall.optJSONArray("functionCalls") ?: return null
            val functionCalls = mutableListOf<GeminiFunctionCall>()
            for (i in 0 until calls.length()) {
                val call = calls.getJSONObject(i)
                val id = call.optString("id", "")
                val name = call.optString("name", "")
                if (id.isEmpty() || name.isEmpty()) continue
                val argsObj = call.optJSONObject("args")
                val args = mutableMapOf<String, Any?>()
                if (argsObj != null) {
                    for (key in argsObj.keys()) {
                        args[key] = argsObj.opt(key)
                    }
                }
                functionCalls.add(GeminiFunctionCall(id, name, args))
            }
            return if (functionCalls.isNotEmpty()) GeminiToolCall(functionCalls) else null
        }
    }
}

// Gemini Tool Call Cancellation

data class GeminiToolCallCancellation(
    val ids: List<String>
) {
    companion object {
        fun fromJSON(json: JSONObject): GeminiToolCallCancellation? {
            val cancellation = json.optJSONObject("toolCallCancellation") ?: return null
            val idsArray = cancellation.optJSONArray("ids") ?: return null
            val ids = mutableListOf<String>()
            for (i in 0 until idsArray.length()) {
                ids.add(idsArray.getString(i))
            }
            return if (ids.isNotEmpty()) GeminiToolCallCancellation(ids) else null
        }
    }
}

// Tool Result

sealed class ToolResult {
    data class Success(val result: String) : ToolResult()
    data class JsonSuccess(val payload: JSONObject) : ToolResult()
    data class Failure(val error: String) : ToolResult()

    fun toJSON(): JSONObject = when (this) {
        is Success -> JSONObject().put("result", result)
        is JsonSuccess -> payload
        is Failure -> JSONObject().put("error", error)
    }
}

// Tool Call Status (for UI)

sealed class ToolCallStatus {
    data object Idle : ToolCallStatus()
    data class Executing(val name: String) : ToolCallStatus()
    data class Completed(val name: String) : ToolCallStatus()
    data class Failed(val name: String, val error: String) : ToolCallStatus()
    data class Cancelled(val name: String) : ToolCallStatus()

    val displayText: String
        get() = when (this) {
            is Idle -> ""
            is Executing -> "Running: $name..."
            is Completed -> "Done: $name"
            is Failed -> "Failed: $name - $error"
            is Cancelled -> "Cancelled: $name"
        }

    val isActive: Boolean
        get() = this is Executing
}

// OpenClaw Connection State

sealed class OpenClawConnectionState {
    data object NotConfigured : OpenClawConnectionState()
    data object Checking : OpenClawConnectionState()
    data object Connected : OpenClawConnectionState()
    data class Unreachable(val message: String) : OpenClawConnectionState()
}

// Tool Declarations (for Gemini setup message)

object ToolDeclarations {
    fun allDeclarationsJSON(): JSONArray {
        return JSONArray()
            .put(startGuidanceJSON())
            .put(guideStepJSON())
            .put(advanceStepJSON())
            .put(focusObjectJSON())
            .put(inspectObjectJSON())
            .put(clearFocusJSON())
            .put(locateObjectJSON())
            .put(executeJSON())
    }

    private fun locateObjectJSON(): JSONObject {
        return JSONObject().apply {
            put("name", "locate_object")
            put(
                "description",
                "Detect and ground an object in the current camera view. Use this when the user asks what an object is, where it is, or asks you to point/highlight something visible right now.",
            )
            put("parameters", JSONObject().apply {
                put("type", "object")
                put("properties", JSONObject().apply {
                    put("query", JSONObject().apply {
                        put("type", "string")
                        put("description", "The object to find in the current view, e.g. wire, screwdriver, charging port, scissors.")
                    })
                    put("includeSegmentation", JSONObject().apply {
                        put("type", "boolean")
                        put("description", "Whether to ask the detector for segmentation-style polygon points in addition to a bounding box.")
                    })
                })
                put("required", JSONArray().put("query"))
            })
            put("behavior", "BLOCKING")
        }
    }

    private fun executeJSON(): JSONObject {
        return JSONObject().apply {
            put("name", "execute")
            put("description", "Your only way to take action. You have no memory, storage, or ability to do anything on your own -- use this tool for everything: sending messages, searching the web, adding to lists, setting reminders, creating notes, research, drafts, scheduling, smart home control, app interactions, or any request that goes beyond answering a question. When in doubt, use this tool.")
            put("parameters", JSONObject().apply {
                put("type", "object")
                put("properties", JSONObject().apply {
                    put("task", JSONObject().apply {
                        put("type", "string")
                        put("description", "Clear, detailed description of what to do. Include all relevant context: names, content, platforms, quantities, etc.")
                    })
                })
                put("required", JSONArray().put("task"))
            })
            put("behavior", "BLOCKING")
        }
    }

    private fun guideStepJSON(): JSONObject {
        return JSONObject().apply {
            put("name", "guide_step")
            put(
                "description",
                "Get the next instruction for the laptop-inspection demo workflow using the current step index and the most recent grounded object result.",
            )
            put("parameters", JSONObject().apply {
                put("type", "object")
                put("properties", JSONObject().apply {
                    put("task", JSONObject().apply {
                        put("type", "string")
                        put("description", "Task name. Defaults to Inspect laptop setup if omitted.")
                    })
                    put("stepIndex", JSONObject().apply {
                        put("type", "integer")
                        put("description", "Zero-based current step index in the demo workflow.")
                    })
                    put("observedLabel", JSONObject().apply {
                        put("type", "string")
                        put("description", "Most recently detected object label, if available.")
                    })
                    put("objectFound", JSONObject().apply {
                        put("type", "boolean")
                        put("description", "Whether the grounding tool found an object for the current step.")
                    })
                })
                put("required", JSONArray().put("stepIndex"))
            })
            put("behavior", "BLOCKING")
        }
    }

    private fun startGuidanceJSON(): JSONObject {
        return JSONObject().apply {
            put("name", "start_guidance")
            put(
                "description",
                "Start a guided task session so the system can decide what object matters next without the user spelling out tool arguments each turn.",
            )
            put("parameters", JSONObject().apply {
                put("type", "object")
                put("properties", JSONObject().apply {
                    put("task", JSONObject().apply {
                        put("type", "string")
                        put("description", "Task to guide, for example 'Inspect laptop setup' or 'Assemble desk lamp'.")
                    })
                    put("sessionId", JSONObject().apply {
                        put("type", "string")
                        put("description", "Optional session identifier. Omit to let the backend create one.")
                    })
                })
            })
            put("behavior", "BLOCKING")
        }
    }

    private fun advanceStepJSON(): JSONObject {
        return JSONObject().apply {
            put("name", "advance_step")
            put(
                "description",
                "Advance the current guidance session to the next step and return the new target query and instruction.",
            )
            put("parameters", JSONObject().apply {
                put("type", "object")
                put("properties", JSONObject().apply {
                    put("sessionId", JSONObject().apply {
                        put("type", "string")
                        put("description", "Guidance session identifier.")
                    })
                })
            })
            put("behavior", "BLOCKING")
        }
    }

    private fun focusObjectJSON(): JSONObject {
        return JSONObject().apply {
            put("name", "focus_object")
            put(
                "description",
                "Find an object in the current camera frame and enter focus/tracking mode so the platform keeps updating the highlight automatically.",
            )
            put("parameters", JSONObject().apply {
                put("type", "object")
                put("properties", JSONObject().apply {
                    put("query", JSONObject().apply {
                        put("type", "string")
                        put("description", "Object to focus on, for example plant, bottle, screwdriver, charging cable.")
                    })
                    put("includeSegmentation", JSONObject().apply {
                        put("type", "boolean")
                        put("description", "Whether to ask for segmentation while focusing.")
                    })
                })
                put("required", JSONArray().put("query"))
            })
            put("behavior", "BLOCKING")
        }
    }

    private fun clearFocusJSON(): JSONObject {
        return JSONObject().apply {
            put("name", "clear_focus")
            put(
                "description",
                "Clear the current focused object, stop tracking mode, and hide the overlay.",
            )
            put("parameters", JSONObject().apply {
                put("type", "object")
                put("properties", JSONObject())
            })
            put("behavior", "BLOCKING")
        }
    }

    private fun inspectObjectJSON(): JSONObject {
        return JSONObject().apply {
            put("name", "inspect_object")
            put(
                "description",
                "Inspect the currently focused object or a named object and return a short description plus info-panel content.",
            )
            put("parameters", JSONObject().apply {
                put("type", "object")
                put("properties", JSONObject().apply {
                    put("query", JSONObject().apply {
                        put("type", "string")
                        put("description", "Optional object label to inspect. If omitted, inspect the current focused object.")
                    })
                })
            })
            put("behavior", "BLOCKING")
        }
    }
}
