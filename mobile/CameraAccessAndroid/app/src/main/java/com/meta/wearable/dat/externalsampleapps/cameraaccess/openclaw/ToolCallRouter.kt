package com.meta.wearable.dat.externalsampleapps.cameraaccess.openclaw

import android.graphics.Bitmap
import android.util.Log
import com.meta.wearable.dat.externalsampleapps.cameraaccess.guidance.GuidanceSessionState
import com.meta.wearable.dat.externalsampleapps.cameraaccess.platform.FocusState
import com.meta.wearable.dat.externalsampleapps.cameraaccess.platform.ObjectInfoPanelState
import com.meta.wearable.dat.externalsampleapps.cameraaccess.vision.DetectionOverlay
import com.meta.wearable.dat.externalsampleapps.cameraaccess.vision.VisionToolClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

class ToolCallRouter(
    private val bridge: OpenClawBridge,
    private val scope: CoroutineScope,
    private val visionToolClient: VisionToolClient,
    private val latestFrameProvider: () -> Bitmap?,
    private val onDetectionOverlay: (DetectionOverlay?) -> Unit,
    private val onGuidanceSession: (GuidanceSessionState) -> Unit,
    private val onFocusState: (FocusState) -> Unit,
    private val onObjectInfoPanel: (ObjectInfoPanelState) -> Unit,
) {
    companion object {
        private const val TAG = "ToolCallRouter"
    }

    private val inFlightJobs = mutableMapOf<String, Job>()
    private var lastDetectedLabel: String? = null
    private var lastFoundObject: Boolean = false
    private var currentGuidanceSessionId: String? = null
    private var currentFocusQuery: String? = null

    fun handleToolCall(
        call: GeminiFunctionCall,
        sendResponse: (JSONObject) -> Unit
    ) {
        val callId = call.id
        val callName = call.name

        Log.d(TAG, "Received: $callName (id: $callId) args: ${call.args}")

        val job = scope.launch {
            val result =
                when (callName) {
                    "start_guidance" -> handleStartGuidance(call)
                    "focus_object" -> handleFocusObject(call)
                    "inspect_object" -> handleInspectObject(call)
                    "clear_focus" -> handleClearFocus(call)
                    "locate_object" -> handleLocateObject(call)
                    "guide_step" -> handleGuideStep(call)
                    "advance_step" -> handleAdvanceStep(call)
                    else -> {
                        val taskDesc = call.args["task"]?.toString() ?: call.args.toString()
                        bridge.delegateTask(task = taskDesc, toolName = callName)
                    }
                }

            if (!coroutineContext[Job]!!.isCancelled) {
                Log.d(TAG, "Result for $callName (id: $callId): $result")
                val response = buildToolResponse(callId, callName, result)
                sendResponse(response)
            } else {
                Log.d(TAG, "Task $callId was cancelled, skipping response")
            }

            inFlightJobs.remove(callId)
        }

        inFlightJobs[callId] = job
    }

    fun cancelToolCalls(ids: List<String>) {
        for (id in ids) {
            inFlightJobs[id]?.let { job ->
                Log.d(TAG, "Cancelling in-flight call: $id")
                job.cancel()
                inFlightJobs.remove(id)
            }
        }
        bridge.setToolCallStatus(ToolCallStatus.Cancelled(ids.firstOrNull() ?: "unknown"))
    }

    fun cancelAll() {
        for ((id, job) in inFlightJobs) {
            Log.d(TAG, "Cancelling in-flight call: $id")
            job.cancel()
        }
        inFlightJobs.clear()
        currentGuidanceSessionId = null
        currentFocusQuery = null
        onDetectionOverlay(null)
        onFocusState(FocusState())
        onObjectInfoPanel(ObjectInfoPanelState())
    }

    private suspend fun handleLocateObject(call: GeminiFunctionCall): ToolResult {
        val query = call.args["query"]?.toString()?.trim().orEmpty()
        val includeSegmentation = (call.args["includeSegmentation"] as? Boolean) ?: false

        if (query.isBlank()) {
            bridge.setToolCallStatus(ToolCallStatus.Failed(call.name, "Missing query"))
            return ToolResult.Failure("Missing required query for locate_object.")
        }

        val frame = latestFrameProvider()
        if (frame == null) {
            bridge.setToolCallStatus(ToolCallStatus.Failed(call.name, "No frame available"))
            Log.e(TAG, "locate_object failed immediately: no frame available for query='$query'")
            return ToolResult.JsonSuccess(
                JSONObject()
                    .put("found", false)
                    .put("label", query)
                    .put("confidence", 0)
                    .put("bbox", JSONObject.NULL)
                    .put("polygon", JSONArray())
                    .put("query", query)
                    .put("provider", "vision-tool")
                    .put("message", "No camera frame is available yet. Ask the user to wait for the live feed."),
            )
        }

        bridge.setToolCallStatus(ToolCallStatus.Executing(call.name))
        Log.d(
            TAG,
            "handleLocateObject start query='$query' includeSegmentation=$includeSegmentation frame=${frame.width}x${frame.height}",
        )

        return try {
            val startedAt = System.currentTimeMillis()
            val detection = visionToolClient.locateObject(frame, query, includeSegmentation)
            val elapsed = System.currentTimeMillis() - startedAt
            lastDetectedLabel = detection.label
            lastFoundObject = detection.found
            val overlay = detection.toOverlay(frame.width, frame.height)
            onDetectionOverlay(overlay)
            if (overlay != null) {
                currentFocusQuery = query
                onFocusState(FocusState.fromOverlay(query, overlay))
            } else {
                currentFocusQuery = null
                onFocusState(FocusState())
            }
            bridge.setToolCallStatus(ToolCallStatus.Completed(call.name))
            Log.d(
                TAG,
                "handleLocateObject success query='$query' found=${detection.found} label='${detection.label}' elapsedMs=$elapsed",
            )
            ToolResult.JsonSuccess(detection.toJSON())
        } catch (e: Exception) {
            onDetectionOverlay(null)
            bridge.setToolCallStatus(ToolCallStatus.Failed(call.name, e.message ?: "Unknown error"))
            Log.e(TAG, "handleLocateObject failure query='$query': ${e.message}", e)
            ToolResult.Failure("locate_object failed: ${e.message ?: "Unknown error"}")
        }
    }

    private suspend fun handleFocusObject(call: GeminiFunctionCall): ToolResult {
        val query = call.args["query"]?.toString()?.trim().orEmpty()
        val includeSegmentation = (call.args["includeSegmentation"] as? Boolean) ?: false

        if (query.isBlank()) {
            bridge.setToolCallStatus(ToolCallStatus.Failed(call.name, "Missing query"))
            return ToolResult.Failure("Missing required query for focus_object.")
        }

        val frame = latestFrameProvider()
        if (frame == null) {
            bridge.setToolCallStatus(ToolCallStatus.Failed(call.name, "No frame available"))
            return ToolResult.Failure("No camera frame is available yet for focus_object.")
        }

        bridge.setToolCallStatus(ToolCallStatus.Executing(call.name))
        Log.d(TAG, "handleFocusObject start query='$query'")

        return try {
            val detection = visionToolClient.locateObject(frame, query, includeSegmentation)
            val overlay = detection.toOverlay(frame.width, frame.height)
            onDetectionOverlay(overlay)
            if (overlay != null) {
                lastDetectedLabel = detection.label
                lastFoundObject = detection.found
                currentFocusQuery = query
                onFocusState(FocusState.fromOverlay(query, overlay))
            } else {
                currentFocusQuery = null
                onFocusState(FocusState())
            }
            bridge.setToolCallStatus(ToolCallStatus.Completed(call.name))
            ToolResult.JsonSuccess(detection.toJSON())
        } catch (e: Exception) {
            onFocusState(FocusState())
            bridge.setToolCallStatus(ToolCallStatus.Failed(call.name, e.message ?: "Unknown error"))
            Log.e(TAG, "handleFocusObject failure: ${e.message}", e)
            ToolResult.Failure("focus_object failed: ${e.message ?: "Unknown error"}")
        }
    }

    private suspend fun handleClearFocus(call: GeminiFunctionCall): ToolResult {
        bridge.setToolCallStatus(ToolCallStatus.Executing(call.name))
        return try {
            onDetectionOverlay(null)
            currentFocusQuery = null
            onFocusState(FocusState())
            onObjectInfoPanel(ObjectInfoPanelState())
            bridge.setToolCallStatus(ToolCallStatus.Completed(call.name))
            ToolResult.JsonSuccess(JSONObject().put("cleared", true))
        } catch (e: Exception) {
            bridge.setToolCallStatus(ToolCallStatus.Failed(call.name, e.message ?: "Unknown error"))
            ToolResult.Failure("clear_focus failed: ${e.message ?: "Unknown error"}")
        }
    }

    private suspend fun handleInspectObject(call: GeminiFunctionCall): ToolResult {
        val requestedQuery = call.args["query"]?.toString()?.trim().takeUnless { it.isNullOrBlank() }
        val query = requestedQuery ?: currentFocusQuery ?: lastDetectedLabel
        val frame = latestFrameProvider()
        bridge.setToolCallStatus(ToolCallStatus.Executing(call.name))
        return try {
            if (query != null && frame != null) {
                val shouldAcquireFocus =
                    currentFocusQuery == null ||
                        requestedQuery != null ||
                        !lastFoundObject

                if (shouldAcquireFocus) {
                    Log.d(TAG, "handleInspectObject auto-focusing query='$query'")
                    val detection = visionToolClient.locateObject(frame, query, false)
                    val overlay = detection.toOverlay(frame.width, frame.height)
                    onDetectionOverlay(overlay)
                    lastDetectedLabel = detection.label
                    lastFoundObject = detection.found
                    if (overlay != null) {
                        currentFocusQuery = query
                        onFocusState(FocusState.fromOverlay(query, overlay))
                    }
                }
            }
            val response = visionToolClient.inspectObject(query, frame)
            onObjectInfoPanel(ObjectInfoPanelState.fromJSON(response))
            bridge.setToolCallStatus(ToolCallStatus.Completed(call.name))
            ToolResult.JsonSuccess(response)
        } catch (e: Exception) {
            bridge.setToolCallStatus(ToolCallStatus.Failed(call.name, e.message ?: "Unknown error"))
            ToolResult.Failure("inspect_object failed: ${e.message ?: "Unknown error"}")
        }
    }

    private suspend fun handleGuideStep(call: GeminiFunctionCall): ToolResult {
        val task = call.args["task"]?.toString()?.trim().orEmpty().ifBlank { "Inspect laptop setup" }
        val sessionId = call.args["sessionId"]?.toString()?.trim().takeUnless { it.isNullOrBlank() } ?: currentGuidanceSessionId
        val stepIndex =
            when (val raw = call.args["stepIndex"]) {
                is Number -> raw.toInt()
                is String -> raw.toIntOrNull() ?: 0
                else -> 0
            }
        val observedLabel = call.args["observedLabel"]?.toString()?.trim().takeUnless { it.isNullOrBlank() } ?: lastDetectedLabel
        val objectFound =
            when (val raw = call.args["objectFound"]) {
                is Boolean -> raw
                is String -> raw.equals("true", ignoreCase = true)
                else -> lastFoundObject
            }

        bridge.setToolCallStatus(ToolCallStatus.Executing(call.name))
        Log.d(
            TAG,
            "handleGuideStep start task='$task' stepIndex=$stepIndex observedLabel='${observedLabel ?: ""}' objectFound=$objectFound",
        )

        return try {
            val startedAt = System.currentTimeMillis()
            val response = visionToolClient.guideStep(task, stepIndex, observedLabel, objectFound, sessionId)
            val elapsed = System.currentTimeMillis() - startedAt
            bridge.setToolCallStatus(ToolCallStatus.Completed(call.name))
            val session = GuidanceSessionState.fromJSON(response)
            currentGuidanceSessionId = session.sessionId
            onGuidanceSession(session)
            Log.d(
                TAG,
                "handleGuideStep success stepIndex=$stepIndex elapsedMs=$elapsed responsePreview='${response.toString().take(240)}'",
            )
            ToolResult.JsonSuccess(response)
        } catch (e: Exception) {
            bridge.setToolCallStatus(ToolCallStatus.Failed(call.name, e.message ?: "Unknown error"))
            Log.e(TAG, "handleGuideStep failure stepIndex=$stepIndex: ${e.message}", e)
            ToolResult.Failure("guide_step failed: ${e.message ?: "Unknown error"}")
        }
    }

    private suspend fun handleStartGuidance(call: GeminiFunctionCall): ToolResult {
        val task = call.args["task"]?.toString()?.trim().takeUnless { it.isNullOrBlank() }
        val sessionId = call.args["sessionId"]?.toString()?.trim().takeUnless { it.isNullOrBlank() }

        bridge.setToolCallStatus(ToolCallStatus.Executing(call.name))
        Log.d(TAG, "handleStartGuidance start task='${task ?: ""}' sessionId='${sessionId ?: ""}'")

        return try {
            val response = visionToolClient.startGuidance(task, sessionId)
            bridge.setToolCallStatus(ToolCallStatus.Completed(call.name))
            val session = GuidanceSessionState.fromJSON(response)
            currentGuidanceSessionId = session.sessionId
            onGuidanceSession(session)
            Log.d(TAG, "handleStartGuidance success response='${response.toString().take(240)}'")
            ToolResult.JsonSuccess(response)
        } catch (e: Exception) {
            bridge.setToolCallStatus(ToolCallStatus.Failed(call.name, e.message ?: "Unknown error"))
            Log.e(TAG, "handleStartGuidance failure: ${e.message}", e)
            ToolResult.Failure("start_guidance failed: ${e.message ?: "Unknown error"}")
        }
    }

    private suspend fun handleAdvanceStep(call: GeminiFunctionCall): ToolResult {
        val sessionId = call.args["sessionId"]?.toString()?.trim().takeUnless { it.isNullOrBlank() }

        bridge.setToolCallStatus(ToolCallStatus.Executing(call.name))
        Log.d(TAG, "handleAdvanceStep start sessionId='${sessionId ?: ""}'")

        return try {
            val response = visionToolClient.advanceStep(sessionId)
            bridge.setToolCallStatus(ToolCallStatus.Completed(call.name))
            val session = GuidanceSessionState.fromJSON(response)
            currentGuidanceSessionId = session.sessionId
            onGuidanceSession(session)
            Log.d(TAG, "handleAdvanceStep success response='${response.toString().take(240)}'")
            ToolResult.JsonSuccess(response)
        } catch (e: Exception) {
            bridge.setToolCallStatus(ToolCallStatus.Failed(call.name, e.message ?: "Unknown error"))
            Log.e(TAG, "handleAdvanceStep failure: ${e.message}", e)
            ToolResult.Failure("advance_step failed: ${e.message ?: "Unknown error"}")
        }
    }

    private fun buildToolResponse(
        callId: String,
        name: String,
        result: ToolResult
    ): JSONObject {
        return JSONObject().apply {
            put("toolResponse", JSONObject().apply {
                put("functionResponses", JSONArray().put(JSONObject().apply {
                    put("id", callId)
                    put("name", name)
                    put("response", result.toJSON())
                }))
            })
        }
    }
}
