# Vision Agent Builder — Hackathon Architecture Research

_Last updated: 2026-03-29_

## Goal

Turn the existing `CameraAccessAndroid` sample into a live demo where Meta Ray-Bans or the phone camera can:

1. observe the world,
2. identify what object matters for the current task step,
3. highlight that object on the live feed, and
4. instruct the user what to do next.

Core demo moment:

> AI points -> user acts -> step advances

## Demo scenario

**Inspect laptop setup**

1. Check power cable
2. Check charging port
3. Verify connection / charging indicator

## Brownfield findings from this app

The existing sample already gives us most of the mobile-side plumbing:

- **Live camera feed exists already** for both glasses and phone mode in `app/src/main/java/com/meta/wearable/dat/externalsampleapps/cameraaccess/stream/StreamViewModel.kt`
- **Frames already become `Bitmap`s** and are forwarded into AI integrations
- **Overlay UI already exists** in `app/src/main/java/com/meta/wearable/dat/externalsampleapps/cameraaccess/ui/StreamScreen.kt`
- **Agent/tool-call plumbing already exists** via Gemini + OpenClaw bridge in:
  - `app/src/main/java/com/meta/wearable/dat/externalsampleapps/cameraaccess/gemini/GeminiSessionViewModel.kt`
  - `app/src/main/java/com/meta/wearable/dat/externalsampleapps/cameraaccess/openclaw/OpenClawBridge.kt`
  - `app/src/main/java/com/meta/wearable/dat/externalsampleapps/cameraaccess/openclaw/ToolCallRouter.kt`

This means the Android app should stay thin:

- stream frames
- render overlays
- play / show guidance
- call remote tools

## Key architecture decision

**Recommended:** make the system **remote-first**.

Do **not** try to make the Android app the place where computer vision, retrieval, and agent reasoning all live.

Use the Android app as the **sensor + renderer**.
Use your MacBook / backend as the **perception + reasoning engine**.

## Why this is the right split

Because the hard part is not "three tools" as a count. The hard part is the grounded loop:

1. capture a usable frame
2. detect / ground the correct object
3. map the result back to UI coordinates
4. keep the target stable enough across time
5. decide the next instruction from task state + docs
6. detect whether the step is complete

That loop is easier to iterate on remotely than inside Android.

## Recommended system architecture

```text
Meta Ray-Bans / Phone Camera
        |
        v
Android sample app
- stream frames
- sample snapshot every 1-2s
- show live overlay box/mask
- voice/text instructions
        |
        v
Remote orchestration service (MacBook / backend)
- observe_scene tool
- retrieve_context tool
- guide_user tool
        |
        +--> vision grounding / detection
        +--> optional segmentation refinement
        +--> task-state reasoning
        +--> docs / visual DB lookup
```

## Recommended MVP tool surface

The best MVP is still roughly **3 tools**, but slightly different from the original framing.

### 1. `observe_scene`
Input:
- latest snapshot
- current step
- optional text prompt like `power cable`, `charging port`, `charging light`

Output:
- detected / grounded objects
- primary target candidate
- bounding box (required)
- mask (optional)
- confidence

Example:

```json
{
  "objects": [
    {"label": "power cable", "bbox": [120, 330, 220, 120], "score": 0.88},
    {"label": "charging port", "bbox": [420, 280, 90, 70], "score": 0.75}
  ],
  "primary_target": {"label": "power cable", "bbox": [120, 330, 220, 120]},
  "frame_id": "f_102"
}
```

### 2. `retrieve_context`
Input:
- task name
- current step
- optionally object labels / scene summary

Output:
- relevant docs / troubleshooting text / prior visual exemplars

Example:

```json
{
  "step": "Check charging port",
  "retrieved_notes": [
    "If the laptop is not charging, reseat the cable fully.",
    "Try another compatible USB-C port if available."
  ]
}
```

### 3. `guide_user`
Input:
- current step
- scene observation
- retrieved docs
- previous step state

Output:
- chosen target object
- instruction text
- whether step is complete
- whether to advance or retry

Example:

```json
{
  "target_object": "power cable",
  "instruction": "Push this cable in until it is fully seated.",
  "step_complete": false,
  "advance_to_step": null
}
```

## Important correction: segmentation should not be a top-level tool

Segmentation is not the product surface.
It is an **implementation detail** inside `observe_scene`.

Why:
- the product value is **deciding what matters + what to do next**
- not every frame needs a perfect mask
- a stable bounding box is often enough for the hackathon demo
- mask generation can be layered in only when the box result is already working

## Best practical perception stack

### Recommended default path

**Grounding / detection first, segmentation second**

#### Grounding / detection
Use an open-vocabulary grounding model to find objects from text prompts such as:
- `power cable`
- `charging port`
- `laptop charging light`

Good candidates:
- **Grounding DINO** for open-vocabulary detection / phrase grounding  
  Source: https://github.com/IDEA-Research/GroundingDINO
- **Grounded SAM 2** style pipelines if you want grounding + segmentation together  
  Source: https://github.com/IDEA-Research/Grounded-SAM-2

#### Segmentation refinement (optional)
If you want prettier highlight overlays after boxes already work:
- **MobileSAM** — lightweight SAM-style segmentation model  
  Source: https://github.com/ChaoningZhang/MobileSAM
- **EdgeSAM** — optimized for edge deployment and supports ONNX / CoreML export  
  Source: https://github.com/chongzhou96/EdgeSAM

### About SAM 3 / SAM 3.1

SAM 3-class models are impressive, but they are **not the first thing to optimize for** in this hackathon architecture.

The main reasons:
- the official `facebookresearch/sam3` repo currently documents a **CUDA GPU-centric** setup (`Python 3.12+`, `PyTorch 2.7+`, `CUDA 12.6+`)  
  Source: https://github.com/facebookresearch/sam3
- your real blocker is usually **grounding the right object**, not generating a prettier mask
- a box-first system gets to demo value much faster

So if you are running on a powerful MacBook, the safer recommendation is:
- start with **grounded bounding boxes**
- add **MobileSAM / EdgeSAM** only if masks noticeably improve the demo
- adopt heavier SAM-family pipelines only after the end-to-end loop is already working

## Architecture options considered

### Option A — Android does everything locally
**Rejected for MVP**

Pros:
- self-contained
- cleaner long-term product story

Cons:
- highest integration risk
- worst iteration speed during hackathon
- pushes CV/runtime complexity into the least convenient environment

### Option B — Thin Android app + remote backend on MacBook
**Recommended**

Pros:
- fastest iteration
- easiest to swap models
- simplest debugging
- reuses existing app well
- aligns with hackathon constraints

Cons:
- depends on network / local server reliability
- less pure as a product architecture

### Option C — Live multimodal model directly does everything with minimal custom backend
**Possible, but not ideal as the only layer**

Pros:
- fast to prototype
- nice demo feel

Cons:
- harder to guarantee deterministic grounded overlays
- tool / state management can get fuzzy
- visual DB and task-state logic become harder to structure cleanly

Best use:
- use the live multimodal model as the **reasoning front-end**, but keep perception / retrieval services explicit behind tools

## Recommended end-to-end loop

```text
frame sampled -> observe_scene -> retrieve_context -> guide_user -> render overlay + speak instruction -> repeat
```

## Minimal data contracts

### Task config

```json
{
  "task": "Inspect laptop",
  "steps": [
    "Check power cable",
    "Check port connection",
    "Verify charging indicator"
  ],
  "docs": "If not charging, reconnect cable or switch port"
}
```

### UI guidance payload

```json
{
  "step_index": 0,
  "step_label": "Check power cable",
  "target": {
    "label": "power cable",
    "bbox": [120, 330, 220, 120],
    "mask": null
  },
  "instruction": "Push this cable in until it is fully seated.",
  "step_complete": false
}
```

## What the website / backend should do

For the demo, the website does **not** need to be a full product.

It only needs to provide enough operator control to support the loop:

### MVP backend responsibilities
- receive snapshots
- run grounding / detection
- optionally refine with segmentation
- retrieve docs / visual examples
- maintain task state
- return overlay + instruction payloads

### Stretch website responsibilities
- define new task JSON configs
- upload docs / troubleshooting notes
- upload reference images / visual exemplars
- inspect past runs
- maybe tune prompts per step

### Not needed for MVP
- multi-user auth system
- full visual training pipeline
- perfect labeling UI
- generalized task marketplace

## Main blocker to achieving all 3 capabilities

Not concept count. **Coordination quality.**

You can absolutely achieve:
- snapshot / observation
- retrieval
- step reasoning

But the failure mode is when they do not agree on the same target.

Example failure:
- detector finds cable
- retriever returns port troubleshooting
- reasoner tells user to check charging light
- overlay still highlights cable

So the central design principle should be:

> One canonical `current_target` object per loop, returned with the instruction payload.

## Practical MVP recommendation

### Phase 1 — get to demo-fast
- remote-first backend on your MacBook
- bounding boxes only
- one scenario: laptop charging inspection
- one task JSON
- step state machine with explicit current step
- docs retrieval can be file-backed or in-memory

### Phase 2 — make it feel magical
- optional segmentation refinement
- stronger phrase grounding prompts
- smoother overlay persistence across frames
- step-complete heuristics

### Phase 3 — stretch
- configurable task editor website
- visual exemplar DB
- multi-task support
- persistent run history

## Final recommendation

Yes, the overall direction is right.

But the cleanest version is:

- **Android app** = camera stream + overlay renderer + voice/text UI
- **Remote backend** = grounding + retrieval + reasoning
- **Primary MVP output** = stable target bounding box + clear instruction + step state
- **Segmentation** = optional enhancement, not the architectural center

If you do that, you can still truthfully say:

> We built a real-time vision guidance agent for the physical world.

## Immediate next build recommendation

1. Add a new overlay payload model in the Android app for a target box + instruction.
2. Add one remote endpoint or tool for `observe_scene` that returns a target bbox.
3. Add one task-state endpoint / tool that returns the next instruction.
4. Hardcode the laptop-inspection task JSON first.
5. Only add segmentation after the box-based loop feels good live.

