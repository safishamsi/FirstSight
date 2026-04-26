# Vision Ops UI Module

## Purpose

Compose UI for the Camera Access sample, including the new Vision Ops console shell, the agent configuration screen, and the live streaming overlays.

## Public API / Entrypoints

- `CameraAccessScaffold`
- `HomeScreen`
- `NonStreamScreen`
- `SettingsScreen`
- `StreamScreen`

## Minimal Example

The app enters this module through `CameraAccessScaffold`, which switches between:

- registration / agent library (`HomeScreen`)
- pre-stream console (`NonStreamScreen`)
- live augmented stream (`StreamScreen`)
- active profile editing (`SettingsScreen`)

## How To Test

- open the app and verify the agent library appears before registration
- open `Settings` and confirm agent fields save back to the active profile
- register or use phone mode, then start a stream
- confirm the live camera stays dominant while transcripts remain visible and the session log opens in a bottom sheet
