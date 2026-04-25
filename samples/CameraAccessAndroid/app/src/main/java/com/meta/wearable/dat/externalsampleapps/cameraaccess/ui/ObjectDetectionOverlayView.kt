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
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import com.meta.wearable.dat.externalsampleapps.cameraaccess.vision.DetectionOverlay
import com.meta.wearable.dat.externalsampleapps.cameraaccess.vision.DirectionHint
import kotlin.math.roundToInt

@Composable
fun ObjectDetectionOverlay(
    overlay: DetectionOverlay,
    modifier: Modifier = Modifier,
) {
    BoxWithConstraints(modifier = modifier) {
        val density = LocalDensity.current
        val canvasWidthPx = with(density) { maxWidth.toPx() }
        val canvasHeightPx = with(density) { maxHeight.toPx() }
        val mappedRect =
            remember(overlay, canvasWidthPx, canvasHeightPx) {
                mapBoundingBox(
                    overlay = overlay,
                    canvasWidth = canvasWidthPx,
                    canvasHeight = canvasHeightPx,
                )
            }
        val polygonPoints =
            remember(overlay, canvasWidthPx, canvasHeightPx) {
                mapPolygon(
                    overlay = overlay,
                    canvasWidth = canvasWidthPx,
                    canvasHeight = canvasHeightPx,
                )
            }

        Canvas(modifier = Modifier.fillMaxSize()) {
            val overlayAlpha =
                overlay.staleSinceMs?.let { staleSince ->
                    val elapsed = (System.currentTimeMillis() - staleSince).coerceAtLeast(0)
                    (1f - (elapsed / 5000f)).coerceIn(0.2f, 1f)
                } ?: 1f

            drawRect(
                color = Color(0xFF00E5FF).copy(alpha = 0.95f * overlayAlpha),
                topLeft = mappedRect.topLeft,
                size = mappedRect.size,
                style = Stroke(width = 3f),
            )

            if (polygonPoints.size >= 3) {
                val path =
                    Path().apply {
                        moveTo(polygonPoints.first().x, polygonPoints.first().y)
                        polygonPoints.drop(1).forEach { point -> lineTo(point.x, point.y) }
                        close()
                    }
                drawPath(
                    path = path,
                    color = Color(0x2200E5FF).copy(alpha = overlayAlpha),
                )
                drawPath(
                    path = path,
                    color = Color(0xFF00E5FF).copy(alpha = 0.85f * overlayAlpha),
                    style = Stroke(width = 2f, cap = StrokeCap.Round),
                )
            }
        }

        Box(
            modifier =
                Modifier.offset {
                        IntOffset(
                            x = mappedRect.left.roundToInt(),
                            y = (mappedRect.top - with(density) { 36.dp.toPx() })
                                .coerceAtLeast(0f)
                                .roundToInt(),
                        )
                    }
                    .background(Color.Black.copy(alpha = 0.48f), RoundedCornerShape(10.dp))
                    .padding(horizontal = 8.dp, vertical = 5.dp),
        ) {
            Text(text = overlay.displayLabel, color = Color.White, fontWeight = FontWeight.Bold)
        }

        if (overlay.directionHint != DirectionHint.CENTER) {
            Box(
                modifier =
                    Modifier.offset {
                            IntOffset(
                                x = mappedRect.left.roundToInt(),
                                y = (mappedRect.bottom + with(density) { 8.dp.toPx() }).roundToInt(),
                            )
                        }
                        .background(Color(0x990B0F14), RoundedCornerShape(10.dp))
                        .padding(horizontal = 8.dp, vertical = 5.dp),
            ) {
                Text(
                    text = overlay.directionHint.displayText,
                    color = Color(0xFF00E5FF),
                    fontWeight = FontWeight.Medium,
                )
            }
        }
    }
}

private fun mapBoundingBox(
    overlay: DetectionOverlay,
    canvasWidth: Float,
    canvasHeight: Float,
): Rect {
    val sourceWidth = overlay.frameWidth.toFloat()
    val sourceHeight = overlay.frameHeight.toFloat()
    val scale = maxOf(canvasWidth / sourceWidth, canvasHeight / sourceHeight)
    val drawnWidth = sourceWidth * scale
    val drawnHeight = sourceHeight * scale
    val offsetX = (canvasWidth - drawnWidth) / 2f
    val offsetY = (canvasHeight - drawnHeight) / 2f

    return Rect(
        left = offsetX + overlay.bbox.x * drawnWidth,
        top = offsetY + overlay.bbox.y * drawnHeight,
        right = offsetX + (overlay.bbox.x + overlay.bbox.width) * drawnWidth,
        bottom = offsetY + (overlay.bbox.y + overlay.bbox.height) * drawnHeight,
    )
}

private fun mapPolygon(
    overlay: DetectionOverlay,
    canvasWidth: Float,
    canvasHeight: Float,
): List<Offset> {
    val sourceWidth = overlay.frameWidth.toFloat()
    val sourceHeight = overlay.frameHeight.toFloat()
    val scale = maxOf(canvasWidth / sourceWidth, canvasHeight / sourceHeight)
    val drawnWidth = sourceWidth * scale
    val drawnHeight = sourceHeight * scale
    val offsetX = (canvasWidth - drawnWidth) / 2f
    val offsetY = (canvasHeight - drawnHeight) / 2f
    return overlay.polygon.map { point ->
        Offset(
            x = offsetX + point.x * drawnWidth,
            y = offsetY + point.y * drawnHeight,
        )
    }
}
