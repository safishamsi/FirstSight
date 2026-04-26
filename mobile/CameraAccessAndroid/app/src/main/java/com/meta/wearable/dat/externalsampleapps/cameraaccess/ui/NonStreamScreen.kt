package com.meta.wearable.dat.externalsampleapps.cameraaccess.ui

import android.widget.Toast
import androidx.activity.compose.LocalActivity
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.meta.wearable.dat.core.types.Permission
import com.meta.wearable.dat.core.types.PermissionStatus
import com.meta.wearable.dat.externalsampleapps.cameraaccess.R
import com.meta.wearable.dat.externalsampleapps.cameraaccess.wearables.WearablesViewModel
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NonStreamScreen(
    viewModel: WearablesViewModel,
    onRequestWearablesPermission: suspend (Permission) -> PermissionStatus,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val activity = LocalActivity.current
    val context = LocalContext.current
    val gettingStartedSheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val scope = rememberCoroutineScope()

    VisionOpsConsole(
        isRegistered = true,
        hasActiveDevice = uiState.hasActiveDevice,
        primaryActionLabel = "Launch Stream",
        primaryActionEnabled = uiState.hasActiveDevice,
        onPrimaryAction = { viewModel.navigateToStreaming(onRequestWearablesPermission) },
        onPhoneMode = viewModel::navigateToPhoneMode,
        onShowSettings = viewModel::showSettings,
        onDisconnect = {
            activity?.let { currentActivity ->
                viewModel.startUnregistration(currentActivity)
            }
                ?: Toast.makeText(context, "Activity not available", Toast.LENGTH_SHORT).show()
        },
        modifier = modifier,
    )

    if (uiState.isGettingStartedSheetVisible) {
        ModalBottomSheet(
            onDismissRequest = { viewModel.hideGettingStartedSheet() },
            sheetState = gettingStartedSheetState,
        ) {
            GettingStartedSheetContent(
                onContinue = {
                    scope.launch {
                        gettingStartedSheetState.hide()
                        viewModel.hideGettingStartedSheet()
                    }
                },
            )
        }
    }
}

@Composable
private fun GettingStartedSheetContent(
    onContinue: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        Text(text = stringResource(R.string.getting_started_title))
        OpsBodyText(text = stringResource(R.string.getting_started_tip_permission), muted = false)
        OpsBodyText(text = stringResource(R.string.getting_started_tip_led), muted = false)
        OpsBodyText(text = stringResource(R.string.getting_started_tip_photo), muted = false)
        OpsPrimaryButton(
            label = stringResource(R.string.getting_started_continue),
            onClick = onContinue,
        )
    }
}
