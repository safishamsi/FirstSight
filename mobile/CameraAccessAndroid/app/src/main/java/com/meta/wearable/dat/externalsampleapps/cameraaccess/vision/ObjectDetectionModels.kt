package com.meta.wearable.dat.externalsampleapps.cameraaccess.vision

import kotlin.math.max
import kotlin.math.min
import org.json.JSONArray
import org.json.JSONObject

data class NormalizedBoundingBox(
    val x: Float,
    val y: Float,
    val width: Float,
    val height: Float,
) {
    fun toJSON(): JSONObject =
        JSONObject()
            .put("x", x)
            .put("y", y)
            .put("width", width)
            .put("height", height)

    companion object {
        fun fromJSON(json: JSONObject?): NormalizedBoundingBox? {
            if (json == null) return null
            return NormalizedBoundingBox(
                x = json.optDouble("x", Double.NaN).toFloat(),
                y = json.optDouble("y", Double.NaN).toFloat(),
                width = json.optDouble("width", Double.NaN).toFloat(),
                height = json.optDouble("height", Double.NaN).toFloat(),
            ).sanitizedOrNull()
        }
    }

    fun sanitizedOrNull(): NormalizedBoundingBox? {
        if (!x.isFinite() || !y.isFinite() || !width.isFinite() || !height.isFinite()) return null
        val left = clamp01(x)
        val top = clamp01(y)
        val right = clamp01(x + width)
        val bottom = clamp01(y + height)
        val sanitizedWidth = right - left
        val sanitizedHeight = bottom - top
        if (sanitizedWidth <= 0f || sanitizedHeight <= 0f) return null
        return copy(x = left, y = top, width = sanitizedWidth, height = sanitizedHeight)
    }
}

data class NormalizedPoint(
    val x: Float,
    val y: Float,
) {
    fun toJSON(): JSONObject = JSONObject().put("x", x).put("y", y)

    companion object {
        fun fromJSON(json: JSONObject?): NormalizedPoint? {
            if (json == null) return null
            val x = json.optDouble("x", Double.NaN).toFloat()
            val y = json.optDouble("y", Double.NaN).toFloat()
            if (!x.isFinite() || !y.isFinite()) return null
            return NormalizedPoint(clamp01(x), clamp01(y))
        }
    }
}

data class ObjectDetectionResult(
    val found: Boolean,
    val label: String,
    val confidence: Float,
    val bbox: NormalizedBoundingBox?,
    val polygon: List<NormalizedPoint> = emptyList(),
    val message: String? = null,
    val query: String? = null,
    val provider: String = "vision-tool",
) {
    fun toJSON(): JSONObject =
        JSONObject()
            .put("found", found)
            .put("label", label)
            .put("confidence", confidence)
            .put("bbox", bbox?.toJSON())
            .put(
                "polygon",
                JSONArray().apply {
                    polygon.forEach { put(it.toJSON()) }
                },
            )
            .put("message", message)
            .put("query", query)
            .put("provider", provider)

    fun toOverlay(frameWidth: Int, frameHeight: Int): DetectionOverlay? {
        val safeBox = bbox ?: return null
        if (!found) return null
        return DetectionOverlay(
            label = label.ifBlank { query ?: "object" },
            query = query ?: label,
            confidence = confidence,
            bbox = safeBox,
            polygon = polygon,
            frameWidth = frameWidth,
            frameHeight = frameHeight,
            provider = provider,
            directionHint = directionForBoundingBox(safeBox),
            lastUpdatedAtMs = System.currentTimeMillis(),
        )
    }

    companion object {
        fun fromJSON(json: JSONObject): ObjectDetectionResult {
            val polygon =
                json.optJSONArray("polygon").toPointList()
                    .ifEmpty {
                        if (json.optBoolean("found", false)) {
                            NormalizedBoundingBox.fromJSON(json.optJSONObject("bbox"))?.toRectanglePolygon()
                                ?: emptyList()
                        } else {
                            emptyList()
                        }
                    }

            return ObjectDetectionResult(
                found = json.optBoolean("found", false),
                label = json.optString("label", ""),
                confidence = json.optDouble("confidence", 0.0).toFloat(),
                bbox = NormalizedBoundingBox.fromJSON(json.optJSONObject("bbox")),
                polygon = polygon,
                message = json.optString("message").takeIf { it.isNotBlank() },
                query = json.optString("query").takeIf { it.isNotBlank() },
                provider = json.optString("provider", "vision-tool"),
            )
        }
    }
}

data class DetectionOverlay(
    val label: String,
    val query: String,
    val confidence: Float,
    val bbox: NormalizedBoundingBox,
    val polygon: List<NormalizedPoint>,
    val frameWidth: Int,
    val frameHeight: Int,
    val provider: String,
    val directionHint: DirectionHint,
    val lastUpdatedAtMs: Long,
    val staleSinceMs: Long? = null,
) {
    val displayLabel: String
        get() = if (query.equals(label, ignoreCase = true)) {
            "$label ${(confidence * 100).toInt()}%"
        } else {
            "$query -> $label ${(confidence * 100).toInt()}%"
        }

    fun withStaleSince(staleSinceMs: Long): DetectionOverlay = copy(staleSinceMs = staleSinceMs)
}

enum class DirectionHint(val displayText: String) {
    LEFT("look left"),
    RIGHT("look right"),
    UP("look up"),
    DOWN("look down"),
    CENTER("centered"),
}

private fun directionForBoundingBox(bbox: NormalizedBoundingBox): DirectionHint {
    val centerX = bbox.x + (bbox.width / 2f)
    val centerY = bbox.y + (bbox.height / 2f)
    return when {
        centerX < 0.35f -> DirectionHint.LEFT
        centerX > 0.65f -> DirectionHint.RIGHT
        centerY < 0.35f -> DirectionHint.UP
        centerY > 0.65f -> DirectionHint.DOWN
        else -> DirectionHint.CENTER
    }
}

private fun JSONArray?.toPointList(): List<NormalizedPoint> {
    if (this == null) return emptyList()
    return buildList {
        for (i in 0 until length()) {
            val point = NormalizedPoint.fromJSON(optJSONObject(i)) ?: continue
            add(point)
        }
    }
}

private fun NormalizedBoundingBox.toRectanglePolygon(): List<NormalizedPoint> =
    listOf(
        NormalizedPoint(x, y),
        NormalizedPoint(x + width, y),
        NormalizedPoint(x + width, y + height),
        NormalizedPoint(x, y + height),
    )

private fun clamp01(value: Float): Float = min(1f, max(0f, value))
