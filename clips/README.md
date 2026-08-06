# Test clips (T4.2)

Real fall footage from the **UR Fall Detection Dataset** (University of
Rzeszów, http://fenix.ur.edu.pl/~mkepski/ds/uf.html — public, per-file
downloads), used here as file sources for `qnet/node/vision.py` verification.
The original `fall-XX-cam0.mp4` files pack depth|RGB side by side in one
640×240 frame; the `*-rgb.mp4` files here are the RGB half only (right 320×240),
cropped on the Ventuno Q — real recordings, unmodified in time.

| Clip | Content | Provenance |
|---|---|---|
| `fall-01-cam0-rgb.mp4` | Walks in, stands, sits, falls | Real (UR Fall fall-01) |
| `fall-02-cam0-rgb.mp4` | Sits on chair, falls, stays down | Real (UR Fall fall-02) — the "exactly one event" clip |
| `fall-03-cam0-rgb.mp4` | Long sit, then falls | Real (UR Fall fall-03) |
| `adl-01-cam0-rgb.mp4` | Daily-living activity that ends **lying down** | Real (UR Fall adl-01) — the model reads deliberate lying as `fallen`; a known, honest limitation (posture, not intent) |
| `fall_recover_fall-STITCHED.mp4` | fall → upright recovery → second fall | **STITCHED, not a real arc**: real UR Fall frames (fall-02 [0:110] + fall-01 [40:90] + fall-03 [160:215]) concatenated to exercise the re-arm rule mechanically. Labelled so nobody quotes it as a real recording. |

T4.3 (human-gated) replaces/extends these with clips recorded in the demo room;
these stay as the regression set that needs no human on camera.

**The `.mp4` files (and the `tests/fixtures/fix_*.jpg` companion frames) are
NOT committed** — UR Fall is public for research but states no explicit
redistribution license, this repo is public AGPL, and the frames show an
identifiable person. The tests need only the committed `fix_*.npz` output
tensors. To reproduce the videos: download `fall-01/02/03-cam0.mp4` and
`adl-01-cam0.mp4` from the dataset page, crop to the right 320×240 half (the
RGB side of the depth|RGB pack); for the stitched arc concatenate
fall-02 [frames 0:110] + fall-01 [40:90] + fall-03 [160:215].

Dataset citation: Kwolek, B., Kepski, M., "Human fall detection on embedded
platform using depth maps and wireless accelerometer", Computer Methods and
Programs in Biomedicine, 117(3), 2014.
