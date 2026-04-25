# Meta Wearables DAT SDK

> Full API reference: https://wearables.developer.meta.com/llms.txt?full=true
> Developer docs: https://wearables.developer.meta.com/docs/develop/

## Code style


## Architecture

The SDK is organized into three modules:
- **mwdat-core**: Device discovery, registration, permissions, device selectors
- **mwdat-camera**: StreamSession, VideoFrame, photo capture
- **mwdat-mockdevice**: MockDeviceKit for testing without hardware

## Kotlin Patterns

- Use `suspend` functions for async operations — no callbacks
- Use `StateFlow` / `Flow` for observing state changes
- Use `DatResult<T, E>` for error handling — not exceptions
- Prefer immutable collections
- Use `sealed interface` for state hierarchies

## Error Handling

The SDK uses `DatResult<T, E>` for type-safe error handling:

```kotlin
val result = Wearables.someOperation()
result.fold(
    onSuccess = { value -> /* handle success */ },
    onFailure = { error -> /* handle error */ }
)

// Or partial handling:
result.onSuccess { value -> /* handle success */ }
result.onFailure { error -> /* handle error */ }
```

Do **not** use `getOrThrow()` — always handle both paths.

## Naming Conventions

| Suffix | Purpose | Example |
|--------|---------|---------|
| `*Manager` | Long-lived resource management | `RegistrationManager` |
| `*Session` | Short-lived flow component | `StreamSession` |
| `*Result` | DatResult type aliases | `RegistrationResult` |
| `*Error` | Error sealed interfaces | `WearablesError` |

Methods: `get*`, `set*`, `check*`, `request*`, `observe*`

## Imports

```kotlin
import com.meta.wearable.dat.core.Wearables          // Entry point
import com.meta.wearable.dat.camera.StreamSession     // Camera streaming
import com.meta.wearable.dat.camera.types.*            // VideoFrame, PhotoData, etc.
```

For testing:
```kotlin
import com.meta.wearable.dat.mockdevice.MockDeviceKit  // MockDeviceKit
```

## Key Types

- `Wearables` — SDK entry point. Call `Wearables.initialize(context)` at startup
- `StreamSession` — Camera streaming session
- `VideoFrame` — Individual video frame with bitmap data
- `AutoDeviceSelector` — Auto-selects the best available device
- `SpecificDeviceSelector` — Selects a specific device by identifier
- `StreamConfiguration` — Configure video quality, frame rate
- `MockDeviceKit` — Factory for creating simulated devices in tests

## Links

- [Android API Reference](https://wearables.developer.meta.com/docs/reference/android/dat/0.5)
- [Developer Documentation](https://wearables.developer.meta.com/docs/develop/)
- [GitHub Repository](https://github.com/facebook/meta-wearables-dat-android)

## Dev environment tips


Guide for setting up the Meta Wearables Device Access Toolkit in an Android app.

## Prerequisites

- Android Studio, minSdk 26+
- Meta AI companion app installed on test device
- Ray-Ban Meta glasses or Meta Ray-Ban Display glasses (or use MockDeviceKit for development)
- Developer Mode enabled in Meta AI app (Settings > Your glasses > Developer Mode)
- GitHub personal access token with `read:packages` scope

## Step 1: Add the Maven repository

In `settings.gradle.kts`:

```kotlin
val localProperties =
    Properties().apply {
        val localPropertiesPath = rootDir.toPath() / "local.properties"
        if (localPropertiesPath.exists()) {
            load(localPropertiesPath.inputStream())
        }
    }

dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
        maven {
            url = uri("https://maven.pkg.github.com/facebook/meta-wearables-dat-android")
            credentials {
                username = ""
                password = System.getenv("GITHUB_TOKEN") ?: localProperties.getProperty("github_token")
            }
        }
    }
}
```

## Step 2: Declare dependencies

In `libs.versions.toml`:

```toml
[versions]
mwdat = "0.5.0"

[libraries]
mwdat-core = { group = "com.meta.wearable", name = "mwdat-core", version.ref = "mwdat" }
mwdat-camera = { group = "com.meta.wearable", name = "mwdat-camera", version.ref = "mwdat" }
mwdat-mockdevice = { group = "com.meta.wearable", name = "mwdat-mockdevice", version.ref = "mwdat" }
```

In `app/build.gradle.kts`:

```kotlin
dependencies {
    implementation(libs.mwdat.core)
    implementation(libs.mwdat.camera)
    implementation(libs.mwdat.mockdevice)
}
```

## Step 3: Configure AndroidManifest.xml

```xml
<manifest ...>
    <uses-permission android:name="android.permission.BLUETOOTH" />
    <uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
    <uses-permission android:name="android.permission.INTERNET" />

    <application ...>
        <!-- Use 0 in Developer Mode; production apps get ID from Wearables Developer Center -->
        <meta-data
            android:name="com.meta.wearable.mwdat.APPLICATION_ID"
            android:value="0" />

        <activity android:name=".MainActivity" ...>
            <intent-filter>
                <action android:name="android.intent.action.VIEW" />
                <category android:name="android.intent.category.DEFAULT" />
                <category android:name="android.intent.category.BROWSABLE" />
                <data android:scheme="myexampleapp" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

Replace `myexampleapp` with your app's URL scheme.

## Step 4: Initialize the SDK

```kotlin
import com.meta.wearable.dat.core.Wearables

class MyApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        Wearables.initialize(this)
    }
}
```

Calling SDK APIs before initialization yields `WearablesError.NOT_INITIALIZED`.

## Step 5: Register with Meta AI

```kotlin
fun startRegistration(context: Context) {
    Wearables.startRegistration(context)
}
```

Observe registration state:

```kotlin
lifecycleScope.launch {
    Wearables.registrationState.collect { state ->
        // Update UI based on registration state
    }
}
```

## Step 6: Start streaming

```kotlin
import com.meta.wearable.dat.camera.StreamSession
import com.meta.wearable.dat.camera.types.StreamConfiguration
import com.meta.wearable.dat.camera.types.VideoQuality
import com.meta.wearable.dat.core.selectors.AutoDeviceSelector

val session = Wearables.startStreamSession(
    context = context,
    deviceSelector = AutoDeviceSelector(),
    streamConfiguration = StreamConfiguration(
        videoQuality = VideoQuality.MEDIUM,
        frameRate = 24,
    ),
)

lifecycleScope.launch {
    session.videoStream.collect { frame ->
        // Display frame
    }
}

lifecycleScope.launch {
    session.state.collect { state ->
        // Update UI based on stream state
    }
}
```

## Next steps

- [Camera Streaming](camera-streaming.md) — Resolution, frame rate, photo capture
- [MockDevice Testing](mockdevice-testing.md) — Test without hardware
- [Session Lifecycle](session-lifecycle.md) — Handle pause/resume/stop
- [Permissions](permissions-registration.md) — Camera permission flows
- [Full documentation](https://wearables.developer.meta.com/docs/develop/)

## Testing instructions


Guide for testing DAT SDK integrations without physical Meta glasses.

## Overview

MockDeviceKit simulates Meta glasses behavior for development and testing. It provides:
- `MockDeviceKit` — Entry point for creating simulated devices
- `MockRaybanMeta` — Simulated Ray-Ban Meta glasses
- `MockCameraKit` — Simulated camera with configurable video feed and photo capture

## Setup

Add `mwdat-mockdevice` to your Gradle dependencies:

```kotlin
dependencies {
    implementation(libs.mwdat.mockdevice)
}
```

## Creating a mock device

```kotlin
import com.meta.wearable.dat.mockdevice.MockDeviceKit
import com.meta.wearable.dat.mockdevice.api.MockDeviceKitConfig

val mockDeviceKit = MockDeviceKit.getInstance(context)

// Attach fake registration and connectivity (auto-initializes Wearables if needed).
// By default, Wearables.registrationState transitions to Registered.
mockDeviceKit.enable()

// Or start in unregistered state to test registration flows:
// mockDeviceKit.enable(MockDeviceKitConfig(initiallyRegistered = false))

val device = mockDeviceKit.pairRaybanMeta()
```

You can check `mockDeviceKit.isEnabled` to query whether the mock environment is active.

## Simulating device states

```kotlin
// Simulate glasses lifecycle
device.powerOn()
device.unfold()
device.don()    // Simulate wearing the glasses

// Later...
device.doff()   // Simulate removing
device.fold()
device.powerOff()
```

## Setting up mock camera feeds

### Video streaming

```kotlin
val camera = device.getCameraKit()
camera.setCameraFeed(videoUri)
```

### Photo capture

```kotlin
val camera = device.getCameraKit()
camera.setCapturedImage(imageUri)
```

**Note**: Android doesn't transcode video automatically. Mock video files must be in h.265 format. Use FFmpeg to convert:

```bash
ffmpeg -hwaccel videotoolbox -i input.mp4 -c:v hevc_videotoolbox -c:a aac_at -tag:v hvc1 -vf "scale=540:960" output.mov
```

## Writing instrumentation tests

Create a reusable test base class:

```kotlin
import android.content.Context
import androidx.test.ext.junit.rules.ActivityScenarioRule
import androidx.test.platform.app.InstrumentationRegistry
import com.meta.wearable.dat.mockdevice.MockDeviceKit
import com.meta.wearable.dat.mockdevice.api.MockDeviceKitInterface
import org.junit.After
import org.junit.Before
import org.junit.Rule

open class MockDeviceKitTestCase<T : Any>(
    private val activityClass: Class<T>
) {
    @get:Rule
    val scenarioRule = ActivityScenarioRule(activityClass)

    protected lateinit var mockDeviceKit: MockDeviceKitInterface
    protected lateinit var targetContext: Context

    @Before
    open fun setUp() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        targetContext = instrumentation.targetContext
        mockDeviceKit = MockDeviceKit.getInstance(targetContext)
        grantRuntimePermissions()
    }

    @After
    open fun tearDown() {
        mockDeviceKit.disable()
    }

    private fun grantRuntimePermissions() {
        val packageName = targetContext.packageName
        val shell = InstrumentationRegistry.getInstrumentation().uiAutomation
        shell.executeShellCommand("pm grant $packageName android.permission.BLUETOOTH_CONNECT")
        shell.executeShellCommand("pm grant $packageName android.permission.CAMERA")
    }
}
```

## Using MockDeviceKit in the CameraAccess sample

The CameraAccess sample app includes a Debug menu for MockDeviceKit:

1. Tap the **Debug icon** to open the MockDeviceKit menu
2. Tap **Pair RayBan Meta** to create a simulated device
3. Use **PowerOn**, **Unfold**, **Don** to simulate glasses states
4. Select video/image files for mock camera feeds
5. Start streaming to see simulated frames

## Supported media formats

| Type | Formats |
|------|---------|
| Video | h.264 (AVC), h.265 (HEVC) |
| Image | JPEG, PNG |

## Links

- [Mock Device Kit overview](https://wearables.developer.meta.com/docs/mock-device-kit)
- [Android testing guide](https://wearables.developer.meta.com/docs/testing-mdk-android)

## Building and streaming


Guide for implementing camera streaming and photo capture with the DAT SDK.

## Key concepts

- **StreamSession**: Main interface for camera streaming
- **VideoFrame**: Individual video frames from the stream
- **StreamConfiguration**: Configure resolution, frame rate
- **PhotoData**: Still image captured from glasses

## Creating a StreamSession

```kotlin
import com.meta.wearable.dat.camera.types.StreamConfiguration
import com.meta.wearable.dat.camera.types.VideoQuality
import com.meta.wearable.dat.core.selectors.AutoDeviceSelector

val session = Wearables.startStreamSession(
    context = context,
    deviceSelector = AutoDeviceSelector(),
    streamConfiguration = StreamConfiguration(
        videoQuality = VideoQuality.MEDIUM,  // 504x896
        frameRate = 24,
    ),
)
```

### Resolution options

| Quality | Size |
|---------|------|
| `VideoQuality.HIGH` | 720 x 1280 |
| `VideoQuality.MEDIUM` | 504 x 896 |
| `VideoQuality.LOW` | 360 x 640 |

### Frame rate options

Valid values: `2`, `7`, `15`, `24`, `30` FPS.

Lower resolution and frame rate yield higher visual quality due to less Bluetooth compression.

## Observing stream state

`StreamSessionState` transitions: `STARTING` -> `STARTED` -> `STREAMING` -> `STOPPING` -> `STOPPED` -> `CLOSED`

```kotlin
lifecycleScope.launch {
    session.state.collect { state ->
        when (state) {
            StreamSessionState.STREAMING -> {
                // Stream is active, frames flowing
            }
            StreamSessionState.STOPPED -> {
                // Stream ended, release resources
            }
            StreamSessionState.CLOSED -> {
                // Session fully closed
            }
            else -> { /* handle other states */ }
        }
    }
}
```

## Receiving video frames

```kotlin
lifecycleScope.launch {
    session.videoStream.collect { frame ->
        // Display frame bitmap
        updatePreview(frame)
    }
}
```

## Photo capture

```kotlin
session.capturePhoto()
    .onSuccess { photoData ->
        // Handle captured photo data
        val imageBytes = photoData.data
    }
    .onFailure { error ->
        // Handle capture error
    }
```

## Bandwidth and quality

Resolution and frame rate are constrained by Bluetooth Classic bandwidth. The SDK automatically reduces quality when bandwidth is limited:
1. First lowers resolution (e.g., HIGH -> MEDIUM)
2. Then reduces frame rate (e.g., 30 -> 24), never below 15 FPS

Request lower settings for higher visual quality per frame.

## Device selection

```kotlin
// Auto-select best available device
val auto = AutoDeviceSelector()

// Select specific device
val specific = SpecificDeviceSelector(deviceIdentifier = deviceId)
```

## Links

- [StreamSession API reference](https://wearables.developer.meta.com/docs/reference/android/dat/0.5/com_meta_wearable_dat_camera_streamsession)
- [StreamConfiguration API reference](https://wearables.developer.meta.com/docs/reference/android/dat/0.5/com_meta_wearable_dat_camera_types_streamconfiguration)
- [Integration guide](https://wearables.developer.meta.com/docs/build-integration-android)

## Session management


Guide for managing device session states in DAT SDK integrations.

## Overview

The DAT SDK runs work inside sessions. Meta glasses expose two experience types:
- **Device sessions** — sustained access to device sensors and outputs
- **Transactions** — short, system-owned interactions (notifications, "Hey Meta")

Your app observes session state changes — the device decides when to transition.

## Session states

| State | Meaning | App action |
|-------|---------|------------|
| `STOPPED` | Session inactive, not reconnecting | Free resources, wait for user action |
| `RUNNING` | Session active, streaming data | Perform live work |
| `PAUSED` | Temporarily suspended | Hold work, may resume |

## Observing session state

```kotlin
lifecycleScope.launch {
    Wearables.getDeviceSessionState(deviceId).collect { state ->
        when (state) {
            SessionState.RUNNING -> onRunning()
            SessionState.PAUSED -> onPaused()
            SessionState.STOPPED -> onStopped()
        }
    }
}
```

## StreamSession state transitions

```text
STARTING -> STARTED -> STREAMING -> STOPPING -> STOPPED -> CLOSED
```

```kotlin
lifecycleScope.launch {
    session.state.collect { state ->
        // React to state changes
    }
}
```

## Common transitions

The device changes session state when:
- User performs a system gesture that opens another experience
- Another app starts a device session
- User removes or folds the glasses (Bluetooth disconnects)
- User removes the app from Meta AI companion app
- Connectivity between companion app and glasses drops

## Pause and resume

When a session is paused:
- The device keeps the connection alive
- Streams stop delivering data
- The device may resume by returning to `RUNNING`

Your app should **not** attempt to restart while paused — wait for `RUNNING` or `STOPPED`.

## Device availability

```kotlin
lifecycleScope.launch {
    Wearables.devices.collect { devices ->
        // Update list of available glasses
    }
}
```

Key behaviors:
- Closing hinges disconnects Bluetooth -> forces `STOPPED`
- Opening hinges restores Bluetooth but does **not** restart sessions
- Start a new session after the device becomes available again

## Implementation checklist

- [ ] Handle all session states (`RUNNING`, `PAUSED`, `STOPPED`)
- [ ] Monitor device availability before starting work
- [ ] Release resources only after `STOPPED`
- [ ] Don't infer transition causes — rely only on observable state
- [ ] Don't restart during `PAUSED` — wait for system to resume or stop

## Links

- [Session lifecycle documentation](https://wearables.developer.meta.com/docs/lifecycle-events)

## Permissions


Guide for app registration and camera permission flows in the DAT SDK.

## Overview

The DAT SDK separates two concepts:
1. **Registration** — Your app registers with Meta AI to become a permitted integration
2. **Device permissions** — After registration, request specific device permissions (e.g., camera)

All permission grants occur through the Meta AI companion app.

## Registration flow

### Start registration

```kotlin
Wearables.startRegistration(context)
```

This opens the Meta AI app where the user approves your app.

### Observe registration state

```kotlin
lifecycleScope.launch {
    Wearables.registrationState.collect { state ->
        when (state) {
            is RegistrationState.Registered -> {
                // App is registered, can request permissions
            }
            is RegistrationState.Unregistered -> {
                // App is not registered
            }
        }
    }
}
```

### Unregister

```kotlin
Wearables.startUnregistration(context)
```

## Camera permissions

### Check permission status

```kotlin
val status = Wearables.checkPermissionStatus(Permission.CAMERA)
if (status == PermissionStatus.Granted) {
    // Start streaming
}
```

### Request permission

Use the SDK's `RequestPermissionContract` with the Activity Result API:

```kotlin
private var permissionContinuation: CancellableContinuation<PermissionStatus>? = null
private val permissionMutex = Mutex()

private val permissionsResultLauncher =
    registerForActivityResult(Wearables.RequestPermissionContract()) { result ->
        permissionContinuation?.resume(result)
        permissionContinuation = null
    }

suspend fun requestWearablesPermission(permission: Permission): PermissionStatus {
    return permissionMutex.withLock {
        suspendCancellableCoroutine { continuation ->
            permissionContinuation = continuation
            continuation.invokeOnCancellation { permissionContinuation = null }
            permissionsResultLauncher.launch(permission)
        }
    }
}
```

Users can choose:
- **Allow once** — temporary, single-session grant
- **Allow always** — persistent grant

## Multi-device behavior

Users can link multiple glasses to Meta AI. The SDK handles this transparently:
- Permission granted on **any** linked device means your app has access
- You don't need to track which device has permissions
- If all devices disconnect, permissions become unavailable

## Developer Mode vs Production

| Mode | Registration behavior |
|------|----------------------|
| Developer Mode | Registration always allowed (use `APPLICATION_ID` = `0`) |
| Production | Users must be in proper release channel |

For production, get your `APPLICATION_ID` from the [Wearables Developer Center](https://wearables.developer.meta.com/).

## Prerequisites

- Registration requires an internet connection
- Meta AI companion app must be installed
- For Developer Mode: enable in Meta AI > Settings > Your glasses > Developer Mode

## Links

- [Permissions documentation](https://wearables.developer.meta.com/docs/permissions-requests)
- [Getting started guide](https://wearables.developer.meta.com/docs/getting-started-toolkit)
- [Manage projects](https://wearables.developer.meta.com/docs/manage-projects)

## Debugging


Guide for diagnosing common issues with DAT SDK integrations.

## Quick diagnosis

```text
Device not connecting?
|
+-- Is Developer Mode enabled? -> Enable in Meta AI app settings
|
+-- Is device registered? -> Check registrationState
|
+-- Is device in range? -> Bluetooth on, glasses powered on
|
+-- Did you call initialize()? -> Must call Wearables.initialize(context) first
|
+-- Stream not receiving frames? -> Check device connection state
```

## Developer Mode

Developer Mode must be enabled for 3P apps to access device features.

### Enabling Developer Mode

1. Open Meta AI app on phone
2. Go to Settings -> (Your connected glasses)
3. Find "Developer Mode" toggle
4. Toggle ON
5. Device may restart

### Symptoms of Developer Mode disabled

- Registration completes but device never connects
- StreamSession stuck without streaming
- Permission requests fail or never appear

### Common gotchas

- Developer Mode toggles **off** after firmware updates — re-enable it
- Developer Mode is per-device — enable for each glasses pair
- Some features need additional permissions beyond Developer Mode

## StreamSession state issues

### Expected flow

```text
STARTING -> STARTED -> STREAMING -> STOPPING -> STOPPED -> CLOSED
```

### Not receiving frames

- Check that `Wearables.initialize(context)` was called
- Verify device is connected and in range
- Ensure camera permission was granted
- Check that the device selector matches an available device

### Unexpected stop

- Device disconnected (out of range, battery died)
- Channel closed by device
- Error in frame processing

## Version compatibility

Ensure compatible versions of SDK, Meta AI app, and glasses firmware:

| SDK | Meta AI App | Ray-Ban Meta | Meta Ray-Ban Display |
|-----|-------------|--------------|----------------------|
| 0.5.0 | Check [version dependencies](https://wearables.developer.meta.com/docs/version-dependencies) | Check docs | Check docs |
| 0.4.0 | V254 | V20 | V21 |
| 0.3.0 | V249 | V20 | — |

## Known issues

| Issue | Workaround |
|-------|-----------|
| No internet -> registration fails | Internet required for registration |
| Streams started with glasses doffed pause when donned | Unpause by tapping side of glasses |
| `DeviceSession` unreliable with camera stream | Avoid using `DeviceSession` |

## Adding debug logging

```kotlin
import android.util.Log

private const val TAG = "DATWearables"

// In your streaming code:
Log.d(TAG, "Stream state changed to: $state")
Log.e(TAG, "Stream error", exception)
```

## Checklist

- [ ] `Wearables.initialize(context)` called before any API use
- [ ] Developer Mode enabled in Meta AI app
- [ ] Meta AI app updated to compatible version
- [ ] Glasses firmware updated to compatible version
- [ ] Internet connection available for registration
- [ ] Bluetooth permissions granted (`BLUETOOTH_CONNECT`)
- [ ] Correct URL scheme in AndroidManifest.xml intent filter
- [ ] `APPLICATION_ID` meta-data set in manifest

## Links

- [Known issues](https://wearables.developer.meta.com/docs/knownissues)
- [Version dependencies](https://wearables.developer.meta.com/docs/version-dependencies)
- [Troubleshooting discussions](https://github.com/facebook/meta-wearables-dat-android/discussions)

## Sample app


Guide for building a complete DAT SDK app with camera streaming and photo capture.

## Overview

This guide walks through building an Android app that connects to Meta glasses, streams video, and captures photos. Use it as a reference alongside the [CameraAccess sample](https://github.com/facebook/meta-wearables-dat-android/tree/main/samples).

## Project setup

1. Create a new Android Studio project (Compose Activity)
2. Add the Maven repository in `settings.gradle.kts`
3. Add `mwdat-core`, `mwdat-camera`, `mwdat-mockdevice` dependencies
4. Configure `AndroidManifest.xml` (see [Getting Started](getting-started.md))

## App architecture

A typical DAT app has these components:

```text
app/src/main/java/com/example/myapp/
├── MyApplication.kt                # Application class, SDK init
├── MainActivity.kt                 # Registration, permission handling
├── stream/
│   └── StreamViewModel.kt          # Streaming, photo capture
└── ui/
    ├── RegistrationScreen.kt       # Registration UI
    └── StreamScreen.kt             # Video preview, capture
```

## SDK initialization

```kotlin
import com.meta.wearable.dat.core.Wearables

class MyApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        Wearables.initialize(this)
    }
}
```

## Stream ViewModel

```kotlin
import com.meta.wearable.dat.camera.types.StreamConfiguration
import com.meta.wearable.dat.camera.types.StreamSessionState
import com.meta.wearable.dat.camera.types.VideoQuality
import com.meta.wearable.dat.core.Wearables
import com.meta.wearable.dat.core.selectors.AutoDeviceSelector
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class StreamViewModel : ViewModel() {
    private val _streamState = MutableStateFlow<StreamSessionState?>(null)
    val streamState = _streamState.asStateFlow()

    private var session: StreamSession? = null

    fun startStream(context: Context) {
        val streamSession = Wearables.startStreamSession(
            context = context,
            deviceSelector = AutoDeviceSelector(),
            streamConfiguration = StreamConfiguration(
                videoQuality = VideoQuality.MEDIUM,
                frameRate = 24,
            ),
        )
        session = streamSession

        viewModelScope.launch {
            streamSession.state.collect { state ->
                _streamState.value = state
            }
        }

        viewModelScope.launch {
            streamSession.videoStream.collect { frame ->
                // Update UI with frame
            }
        }
    }

    fun stopStream() {
        session?.stop()
        session = null
    }

    fun capturePhoto() {
        session?.capturePhoto()
            ?.onSuccess { photoData ->
                // Handle photo
            }
            ?.onFailure { error ->
                // Handle error
            }
    }
}
```

## Registration handling

```kotlin
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        lifecycleScope.launch {
            Wearables.registrationState.collect { state ->
                // Update registration UI
            }
        }

        lifecycleScope.launch {
            Wearables.devices.collect { devices ->
                // Update device list
            }
        }
    }

    fun register() {
        Wearables.startRegistration(this)
    }

    fun unregister() {
        Wearables.startUnregistration(this)
    }
}
```

## Testing with MockDeviceKit

```kotlin
import com.meta.wearable.dat.mockdevice.MockDeviceKit
import com.meta.wearable.dat.mockdevice.api.MockDeviceKitConfig

fun setupMockDevice(context: Context) {
    val mockDeviceKit = MockDeviceKit.getInstance(context)

    // Attach fake implementations (auto-initializes Wearables if needed).
    // Starts Registered by default. Pass MockDeviceKitConfig(initiallyRegistered = false)
    // to start in unregistered state for testing registration flows.
    mockDeviceKit.enable()

    val device = mockDeviceKit.pairRaybanMeta()
    device.powerOn()
    device.unfold()
    device.don()

    // Set up mock camera feed
    val camera = device.getCameraKit()
    camera.setCameraFeed(videoUri)
}

fun tearDownMockDevice(context: Context) {
    val mockDeviceKit = MockDeviceKit.getInstance(context)
    // Unpairs all mock devices, clears pairedDevices, restores real stack
    mockDeviceKit.disable()
}
```

## Allowed dependencies

Your DAT app should only depend on:
- `mwdat-core` — always required
- `mwdat-camera` — for camera streaming
- `mwdat-mockdevice` — for testing

## Links

- [CameraAccess sample](https://github.com/facebook/meta-wearables-dat-android/tree/main/samples)
- [Full integration guide](https://wearables.developer.meta.com/docs/build-integration-android)
- [Developer documentation](https://wearables.developer.meta.com/docs/develop/)
