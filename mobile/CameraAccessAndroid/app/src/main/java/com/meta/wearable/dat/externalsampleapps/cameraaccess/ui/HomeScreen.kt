package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import android.widget.Toast
import androidx.activity.compose.LocalActivity
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import com.meta.wearable.dat.externalsampleapps.cameraaccess.wearables.WearablesViewModel

@Composable
fun HomeScreen(
    viewModel: WearablesViewModel,
    modifier: Modifier = Modifier,
) {
    val activity = LocalActivity.current
    val context = LocalContext.current

    VisionOpsConsole(
        isRegistered = false,
        hasActiveDevice = false,
        primaryActionLabel = "Connect",
        primaryActionEnabled = true,
        onPrimaryAction = {
            activity?.let { currentActivity ->
                viewModel.startRegistration(currentActivity)
            }
                ?: Toast.makeText(context, "Activity not available", Toast.LENGTH_SHORT).show()
        },
        onPhoneMode = viewModel::navigateToPhoneMode,
        onShowSettings = viewModel::showSettings,
        onDisconnect = null,
        modifier = modifier,
    )
}
