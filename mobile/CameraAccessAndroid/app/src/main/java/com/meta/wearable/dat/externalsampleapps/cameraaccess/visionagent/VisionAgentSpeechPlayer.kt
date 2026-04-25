package com.meta.wearable.dat.externalsampleapps.cameraaccess.visionagent

import android.app.Application
import android.speech.tts.TextToSpeech
import android.util.Log
import java.util.Locale

class VisionAgentSpeechPlayer(application: Application) : TextToSpeech.OnInitListener {
    companion object {
        private const val TAG = "VisionAgentSpeechPlayer"
    }

    private val textToSpeech = TextToSpeech(application.applicationContext, this)
    private var ready = false
    private var pendingText: String? = null

    override fun onInit(status: Int) {
        ready = status == TextToSpeech.SUCCESS
        if (!ready) {
            Log.e(TAG, "TextToSpeech init failed with status=$status")
            return
        }
        textToSpeech.language = Locale.US
        pendingText?.let {
            pendingText = null
            speak(it)
        }
    }

    fun speak(text: String) {
        if (text.isBlank()) return
        if (!ready) {
            pendingText = text
            return
        }
        textToSpeech.speak(text, TextToSpeech.QUEUE_FLUSH, null, "vision-agent-guidance")
    }

    fun stop() {
        if (ready) {
            textToSpeech.stop()
        }
    }

    fun shutdown() {
        textToSpeech.stop()
        textToSpeech.shutdown()
    }
}
