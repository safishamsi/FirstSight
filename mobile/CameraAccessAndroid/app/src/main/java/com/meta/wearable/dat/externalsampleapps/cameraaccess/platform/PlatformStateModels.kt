package com.meta.wearable.dat.externalsampleapps.cameraaccess.platform

import com.meta.wearable.dat.externalsampleapps.cameraaccess.vision.DetectionOverlay
import com.meta.wearable.dat.externalsampleapps.cameraaccess.vision.DirectionHint

data class FocusState(
    val active: Boolean = false,
    val query: String? = null,
    val label: String? = null,
    val overlay: DetectionOverlay? = null,
    val directionHint: DirectionHint = DirectionHint.CENTER,
    val tracking: Boolean = false,
) {
    companion object {
        fun fromOverlay(query: String, overlay: DetectionOverlay): FocusState =
            FocusState(
                active = true,
                query = query,
                label = overlay.label,
                overlay = overlay,
                directionHint = overlay.directionHint,
                tracking = true,
            )
    }
}
