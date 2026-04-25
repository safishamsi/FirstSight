package com.meta.wearable.dat.externalsampleapps.cameraaccess.platform

object ObjectMentionResolver {
    private val objectAliases =
        mapOf(
            "bottle" to listOf("bottle", "water bottle", "cup", "drink", "water"),
            "plant" to listOf("plant", "potted plant"),
            "screwdriver" to listOf("screwdriver", "driver"),
            "scissors" to listOf("scissors"),
            "charging cable" to listOf("charging cable", "power cable", "cable", "wire"),
            "charging port" to listOf("charging port", "usb-c port", "port"),
        )

    fun resolve(text: String): String? {
        val normalized = text.lowercase()
        return objectAliases.entries.firstOrNull { (_, aliases) ->
            aliases.any { alias -> normalized.contains(alias) }
        }?.key
    }
}
