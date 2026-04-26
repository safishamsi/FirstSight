package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentSpatialBox
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentSpatialOverlay
import com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent.VisionAgentSpatialPoint
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

@Composable
fun VisionAgentSpatialOverlays(
    overlays: List<VisionAgentSpatialOverlay>,
    frameWidth: Int,
    frameHeight: Int,
    modifier: Modifier = Modifier,
) {
    if (overlays.isEmpty() || frameWidth <= 0 || frameHeight <= 0) return

    BoxWithConstraints(modifier = modifier) {
        val density = LocalDensity.current
        val canvasWidthPx = with(density) { maxWidth.toPx() }
        val canvasHeightPx = with(density) { maxHeight.toPx() }

        Canvas(modifier = Modifier.fillMaxSize()) {
            overlays.forEach { overlay ->
                val color = overlay.colorOrDefault()
                when (overlay.kind) {
                    "box" -> {
                        val box = overlay.box ?: return@forEach
                        val rect =
                            mapBoundingBox(
                                box = box,
                                frameWidth = frameWidth,
                                frameHeight = frameHeight,
                                canvasWidth = canvasWidthPx,
                                canvasHeight = canvasHeightPx,
                            )
                        drawRect(
                            color = color.copy(alpha = 0.95f),
                            topLeft = rect.topLeft,
                            size = rect.size,
                            style = Stroke(width = 3f),
                        )
                    }

                    "trajectory", "polygon" -> {
                        if (overlay.points.size < 2) return@forEach
                        val mappedPoints =
                            overlay.points.map {
                                mapPoint(
                                    point = it,
                                    frameWidth = frameWidth,
                                    frameHeight = frameHeight,
                                    canvasWidth = canvasWidthPx,
                                    canvasHeight = canvasHeightPx,
                                )
                            }
                        val path =
                            Path().apply {
                                moveTo(mappedPoints.first().x, mappedPoints.first().y)
                                mappedPoints.drop(1).forEach { lineTo(it.x, it.y) }
                            }
                        drawPath(
                            path = path,
                            color = color.copy(alpha = if (overlay.emphasis == "ghost") 0.35f else 0.82f),
                            style = Stroke(width = 6f),
                        )
                        mappedPoints.forEachIndexed { index, point ->
                            drawCircle(
                                color = color.copy(alpha = if (index == 0) 1f else 0.82f),
                                radius = if (index == 0) 9f else 6f,
                                center = point,
                            )
                        }
                    }

                    "point" -> {
                        val point = overlay.point ?: return@forEach
                        val mappedPoint =
                            mapPoint(
                                point = point,
                                frameWidth = frameWidth,
                                frameHeight = frameHeight,
                                canvasWidth = canvasWidthPx,
                                canvasHeight = canvasHeightPx,
                            )
                        drawCircle(
                            color = color,
                            radius = 9f,
                            center = mappedPoint,
                        )
                    }
                }
            }
        }

        overlays.forEach { overlay ->
            val color = overlay.colorOrDefault()
            val label = overlay.label ?: overlay.text ?: overlay.kind
            when (overlay.kind) {
                "box" -> {
                    val box = overlay.box ?: return@forEach
                    val rect =
                        remember(overlay.id, canvasWidthPx, canvasHeightPx, frameWidth, frameHeight) {
                            mapBoundingBox(
                                box = box,
                                frameWidth = frameWidth,
                                frameHeight = frameHeight,
                                canvasWidth = canvasWidthPx,
                                canvasHeight = canvasHeightPx,
                            )
                        }
                    OverlayLabel(
                        text = label,
                        color = color,
                        x = rect.left,
                        y = (rect.top - with(density) { 34.dp.toPx() }).coerceAtLeast(0f),
                    )
                }

                "point" -> {
                    val point = overlay.point ?: return@forEach
                    val mappedPoint =
                        remember(overlay.id, canvasWidthPx, canvasHeightPx, frameWidth, frameHeight) {
                            mapPoint(
                                point = point,
                                frameWidth = frameWidth,
                                frameHeight = frameHeight,
                                canvasWidth = canvasWidthPx,
                                canvasHeight = canvasHeightPx,
                            )
                        }
                    OverlayLabel(
                        text = label,
                        color = color,
                        x = mappedPoint.x + with(density) { 8.dp.toPx() },
                        y = (mappedPoint.y - with(density) { 18.dp.toPx() }).coerceAtLeast(0f),
                    )
                }

                "trajectory", "polygon" -> {
                    val firstPoint = overlay.points.firstOrNull() ?: return@forEach
                    val mappedPoint =
                        remember(overlay.id, canvasWidthPx, canvasHeightPx, frameWidth, frameHeight) {
                            mapPoint(
                                point = firstPoint,
                                frameWidth = frameWidth,
                                frameHeight = frameHeight,
                                canvasWidth = canvasWidthPx,
                                canvasHeight = canvasHeightPx,
                            )
                        }
                    OverlayLabel(
                        text = label,
                        color = color,
                        x = mappedPoint.x + with(density) { 8.dp.toPx() },
                        y = (mappedPoint.y - with(density) { 18.dp.toPx() }).coerceAtLeast(0f),
                    )
                }

                "text" -> {
                    OverlayLabel(
                        text = label,
                        color = color,
                        x = with(density) { 14.dp.toPx() },
                        y = with(density) { 14.dp.toPx() },
                    )
                }
            }
        }
    }
}

@Composable
private fun OverlayLabel(
    text: String,
    color: Color,
    x: Float,
    y: Float,
) {
    Box(
        modifier =
            Modifier
                .offset { IntOffset(x.roundToInt(), y.roundToInt()) }
                .background(color = color.copy(alpha = 0.92f), shape = RoundedCornerShape(10.dp))
                .padding(horizontal = 8.dp, vertical = 5.dp),
    ) {
        Text(
            text = text,
            color = Color.Black,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

private fun VisionAgentSpatialOverlay.colorOrDefault(): Color =
    parseColor(colorHex) ?: Color(0xFF00E5FF)

private fun parseColor(hex: String?): Color? {
    if (hex.isNullOrBlank()) return null
    val normalized = hex.removePrefix("#")
    val value =
        when (normalized.length) {
            6 -> normalized.toLongOrNull(16)?.or(0xFF000000)
            8 -> normalized.toLongOrNull(16)
            else -> null
        } ?: return null
    return Color(value.toULong())
}

private fun mapBoundingBox(
    box: VisionAgentSpatialBox,
    frameWidth: Int,
    frameHeight: Int,
    canvasWidth: Float,
    canvasHeight: Float,
): Rect {
    val sourceWidth = frameWidth.toFloat()
    val sourceHeight = frameHeight.toFloat()
    val scale = max(canvasWidth / sourceWidth, canvasHeight / sourceHeight)
    val drawnWidth = sourceWidth * scale
    val drawnHeight = sourceHeight * scale
    val offsetX = (canvasWidth - drawnWidth) / 2f
    val offsetY = (canvasHeight - drawnHeight) / 2f
    return Rect(
        left = offsetX + normalizeAxis(box.xmin) * drawnWidth,
        top = offsetY + normalizeAxis(box.ymin) * drawnHeight,
        right = offsetX + normalizeAxis(box.xmax) * drawnWidth,
        bottom = offsetY + normalizeAxis(box.ymax) * drawnHeight,
    )
}

private fun mapPoint(
    point: VisionAgentSpatialPoint,
    frameWidth: Int,
    frameHeight: Int,
    canvasWidth: Float,
    canvasHeight: Float,
): Offset {
    val sourceWidth = frameWidth.toFloat()
    val sourceHeight = frameHeight.toFloat()
    val scale = max(canvasWidth / sourceWidth, canvasHeight / sourceHeight)
    val drawnWidth = sourceWidth * scale
    val drawnHeight = sourceHeight * scale
    val offsetX = (canvasWidth - drawnWidth) / 2f
    val offsetY = (canvasHeight - drawnHeight) / 2f
    return Offset(
        x = offsetX + normalizeAxis(point.x) * drawnWidth,
        y = offsetY + normalizeAxis(point.y) * drawnHeight,
    )
}

private fun normalizeAxis(value: Float): Float = min(1f, max(0f, value / 1000f))
