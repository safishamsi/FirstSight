package com.meta.wearable.dat.externalsampleapps.cameraaccess.platform

import org.json.JSONArray
import org.json.JSONObject

data class SearchResultItem(
    val title: String,
    val url: String,
    val snippet: String,
)

data class ObjectInfoPanelState(
    val visible: Boolean = false,
    val label: String = "",
    val title: String = "",
    val description: String = "",
    val usedFor: String? = null,
    val searchResults: List<SearchResultItem> = emptyList(),
) {
    companion object {
        fun fromJSON(json: JSONObject): ObjectInfoPanelState =
            ObjectInfoPanelState(
                visible = true,
                label = json.optString("label", ""),
                title = json.optString("title", ""),
                description = json.optString("description", ""),
                usedFor = json.optString("used_for").takeIf { it.isNotBlank() },
                searchResults = json.optJSONArray("search_results").toSearchResults(),
            )
    }
}

private fun JSONArray?.toSearchResults(): List<SearchResultItem> {
    if (this == null) return emptyList()
    return buildList {
        for (i in 0 until length()) {
            val obj = optJSONObject(i) ?: continue
            add(
                SearchResultItem(
                    title = obj.optString("title", ""),
                    url = obj.optString("url", ""),
                    snippet = obj.optString("snippet", ""),
                )
            )
        }
    }
}
