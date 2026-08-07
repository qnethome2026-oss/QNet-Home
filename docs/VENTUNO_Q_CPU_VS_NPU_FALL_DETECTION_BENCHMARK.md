# Ventuno Q (QCS8300): CPU vs. NPU Benchmark for the Fall Detection Model

Measured comparison of running `melihuzunoglu/human-fall-detection` (YOLO11n,
640×640) on the Ventuno Q board's CPU (via ONNX Runtime) versus its Hexagon
NPU (via QNN `qnn-net-run`), across latency, utilization, power, and derived
energy efficiency. Every number below is measured on the real board unless
explicitly marked as derived/estimated. Written 2026-08-06/07 as a follow-up
to `models/fall-detection/README.md`, which covers how the model was compiled
and deployed in the first place — read that first if you need the conversion
pipeline, not just these results.

## TL;DR

| | CPU (ONNX Runtime) | NPU (Hexagon HTP v75) | NPU advantage |
|---|---|---|---|
| Latency (mean, end-to-end) | 194.7 ms | 46.4 ms | **4.2× faster** |
| Latency (pure compute only) | — | 32.5 ms | **6.0× faster** than CPU wall-clock |
| Host CPU utilization | 604% (~6 of 8 cores) | 36% (orchestration only) | NPU frees the CPU almost entirely |
| Peak host RAM | 134 MB | 19.2 MB | **7× less host memory** |
| Power draw (board total, avg) | 11.12 W | 9.38 W | Lower peak draw |
| Power draw above idle | +3.31 W | +1.79 W | Lower marginal draw too |
| Energy per inference (marginal) | 644 mJ | 83 mJ | **~7.8× more energy-efficient** |
| Energy per inference (gross, whole-board) | 2166 mJ | 435 mJ | **~5.0× more energy-efficient** |
| Inferences per joule (marginal) | 1.55 | 12.04 | — |

**Bottom line:** on this board, the NPU path is faster, uses far less host
CPU/RAM, and does roughly 5-8× more inferences per joule than the CPU path,
depending on whether you count the board's idle draw as part of the cost.
Both paths ran the same precision (FP32, unquantized) — this is not an
FP32-vs-INT8 comparison, it's the same model on two different compute units.

## Environment

| | |
|---|---|
| Board | Ventuno Q (Arduino UNO Q), SoC **QCS8300** |
| CPU | big.LITTLE: 4× Cortex-A55 (up to 1.958 GHz) + 4× Cortex-A78C (up to 2.362 GHz), 8 cores total |
| NPU | Hexagon HTP **v75** |
| RAM | 14 GiB |
| OS | Ubuntu 24.04.4 LTS, kernel `6.8.0-1080-qcom`, aarch64 |
| QNN SDK | QAIRT 2.46.0 (`qnn-net-run`) |
| CPU inference runtime | `onnxruntime` 1.28.0 (CPUExecutionProvider), Python 3.12.3 |
| Model (CPU path) | `best.onnx` (FP32 ONNX export) |
| Model (NPU path) | `best.bin` (FP32 QNN context binary, compiled for `aihub_device="QCS8550 (Proxy)"` / HTP v75 — see `models/fall-detection/README.md`) |
| Power sensor | `hwmon5` = **INA232** current/power monitor on the board's 12V input rail (`/sys/class/hwmon/hwmon5/power1_input`, µW) — measures **whole-board** power draw, not an isolated SoC/rail reading |

## Methodology — exactly what was run and how

All commands below were run over SSH (`plink.exe -ssh -pw ... -batch -hostkey ...
arduino@10.73.51.123`) from the Windows dev host. Nothing here needs the MCP
server — it's local benchmarking against the artifacts already on the board.

### 1. Idle power baseline (run twice, once before each workload)

```bash
for i in $(seq 1 30); do
  date +%s.%N
  cat /sys/class/hwmon/hwmon5/power1_input
  sleep 0.1
done > power_idle.log
```
30 samples at 100 ms spacing (~3 s window). Averaged the `power1_input`
readings (µW → W). Two runs, bracketing the CPU and NPU workloads
respectively, to catch any baseline drift between them:
- Idle #1 (before CPU run): **7.813 W**
- Idle #2 (before NPU run): **7.589 W**

The ~0.22 W difference between the two idle samples is itself a useful
error bar on the power numbers below — treat power figures as accurate to
roughly ±0.2-0.3 W, not more.

### 2. CPU benchmark

`bench_cpu.py`, pushed to `/data/local/tmp/quad/models/`:
```python
import json, time
import numpy as np
import onnxruntime as ort

N = 20
sess = ort.InferenceSession("best.onnx", providers=["CPUExecutionProvider"])
input_name = sess.get_inputs()[0].name
x = np.random.rand(1, 3, 640, 640).astype(np.float32)

for _ in range(3):          # warm-up, not timed
    sess.run(None, {input_name: x})

latencies = []
for _ in range(N):
    t0 = time.perf_counter()
    sess.run(None, {input_name: x})
    latencies.append((time.perf_counter() - t0) * 1000.0)
# ... mean/median/std/min/max computed and dumped to bench_cpu_result.json
```
`onnxruntime` was installed on-device via `pip3 install --break-system-packages
onnxruntime numpy` (plain CPU wheel — no `onnxruntime-qnn`, so this is a true
CPU-only path, not NPU-accelerated ONNX Runtime).

Run, with concurrent power sampling and OS-level resource accounting:
```bash
cd /data/local/tmp/quad/models
timeout 55 bash -c 'while true; do date +%s.%N; cat /sys/class/hwmon/hwmon5/power1_input; sleep 0.1; done' > power_cpu.log 2>/dev/null &
echo $! > sampler.pid
/usr/bin/time -v python3 bench_cpu.py > cpu_stdout.log 2> cpu_time.log
kill $(cat sampler.pid); sleep 0.5; kill -9 $(cat sampler.pid) 2>/dev/null
```
`/usr/bin/time -v` (GNU time, not the bash builtin) gives CPU%, peak RSS, and
context-switch counts for the whole `python3 bench_cpu.py` process — this
includes model load + 3 warm-up + 20 timed runs, so it's a slight
overestimate of steady-state resource use, but the *latency* numbers
(`bench_cpu_result.json`) only cover the 20 timed, warmed-up runs.

**Gotcha hit and fixed:** the first attempt piped `cd DIR && (sampler) &` as
one shell line — due to `&`/`&&` precedence, the *entire* `cd && sampler`
group got backgrounded, so the foregrounded `python3 bench_cpu.py` never
actually ran in `DIR` and failed instantly (`No such file or directory`).
Worse, the sampler's `while true` loop (no `timeout` on the first attempt)
then ran unattended for **~21 hours** until the SSH session eventually
dropped (`FATAL ERROR: Network error: Software caused connection abort`),
leaving a 23 MB stray `power_cpu.log`. Fixed by separating the `cd` with `;`
instead of `&&` before backgrounding, writing the sampler PID to a file
instead of relying on `$!` surviving a one-linear, and wrapping the sampler
in `timeout 55` as a hard safety net regardless.

### 3. NPU benchmark

To get a genuine steady-state per-inference number (not skewed by
context-load overhead), 20 inferences were run in a **single**
`qnn-net-run` invocation rather than 20 separate process launches — QNN's
`--input_list` accepts multiple lines, each triggering one inference within
the same loaded context:
```bash
for i in $(seq 1 20); do echo 'images:=input_0.raw'; done > input_list_20.txt
```
(Same input file reused 20× — content doesn't affect timing, and the model's
compute path doesn't depend on pixel values.)

```bash
cd /data/local/tmp/quad/models
rm -rf out_bench
timeout 55 bash -c 'while true; do date +%s.%N; cat /sys/class/hwmon/hwmon5/power1_input; sleep 0.1; done' > power_npu.log 2>/dev/null &
echo $! > sampler2.pid
/usr/bin/time -v qnn-net-run --backend /usr/lib/libQnnHtp.so --retrieve_context best.bin \
  --input_list input_list_20.txt --output_dir out_bench --profiling_level detailed \
  > npu_stdout.log 2> npu_time.log
kill $(cat sampler2.pid); sleep 0.5; kill -9 $(cat sampler2.pid) 2>/dev/null
```
All 20 `Result_N` outputs were produced successfully. The binary profiling
log (`out_bench/qnn-profiling-data_0.log`) was pulled back to the Windows
host and decoded with:
```bash
C:\Qualcomm\AIStack\QAIRT\2.36.0.250627\bin\aarch64-windows-msvc\qnn-profile-viewer.exe \
  --input_log=<path>
```
This is the same board/tool pairing documented in
`models/fall-detection/README.md` (the board has no `qnn-profile-viewer`
itself; the arm64 Windows build was used since this dev host is win-arm64).

The profiler reports two numbers, both used below for different purposes:
- **"Execute Stats (Average)" NetRun**: 32,519 µs = **32.5 ms** — averaged
  over the 20 in-process runs, this is the actual HTP compute+RPC time per
  inference, excluding the one-time context load/init.
- **"Execute Stats (Overall)" IPS**: 21.5353 inf/sec → **46.4 ms**/inference
  — this is 1/IPS, and *does* include per-call I/O and bookkeeping overhead
  across the batch, making it the fairer like-for-like comparison against
  the CPU path's end-to-end `time.perf_counter()` measurement.

Only **11 power samples** landed inside the 1.27 s total run window (at
100 ms spacing) — noticeably fewer than the CPU run's ~48 samples over its
~5.5 s window. Treat the NPU power figure as lower-confidence than the CPU
one for exactly this reason: fewer samples means more noise in the average.

## Results

### Latency

| Metric | CPU | NPU (pure execute) | NPU (end-to-end, incl. I/O) |
|---|---|---|---|
| Mean | 194.7 ms | 32.5 ms | 46.4 ms |
| Median | 197.9 ms | — | — |
| Std dev | 60.9 ms | — | — |
| Min | 118.2 ms | — | — |
| Max | 308.8 ms | — | — |
| N | 20 | 20 (batched, 1 process) | 20 (batched, 1 process) |

The CPU numbers have real spread (min 118 ms, max 309 ms, std ~61 ms) —
plausibly big.LITTLE scheduling variance (inferences landing on A55 vs A78C
cores across runs) rather than measurement noise, since each run used
identical input and the model/session was already warmed up. The NPU number
is a single averaged figure from the profiler, not a per-run list, so its
own run-to-run spread isn't visible from this data — worth re-running with
per-call profiling if that variance matters later.

### Utilization

| Metric | CPU | NPU |
|---|---|---|
| Host CPU % (`/usr/bin/time -v`) | 604% (of 800% max, i.e. ~6 of 8 cores) | 36% |
| Peak host RSS | 134 MB (137,288 KB) | 19.2 MB (19,608 KB) |
| Compute-side parallelism | ONNX Runtime default intra-op threading across CPU cores | 4 HVX threads (Hexagon vector units) — same thread count as the earlier single-inference IQ-9075 and Ventuno Q runs |

The CPU path saturates most of the board's CPU cores for the duration of
each inference — meaning it directly competes with anything else running on
the board (e.g. the room-node's other services, per `docs/DESIGN.md`). The
NPU path leaves the CPU almost entirely free.

### Power and energy

| Metric | CPU | NPU |
|---|---|---|
| Idle baseline | 7.813 W | 7.589 W |
| Avg power during workload (gross) | 11.121 W | 9.378 W |
| Avg power above idle (marginal) | 3.308 W | 1.789 W |
| Energy per inference (gross) | 2166 mJ | 435 mJ |
| Energy per inference (marginal) | 644 mJ | 83 mJ |
| Inferences per joule (marginal) | 1.55 | 12.04 |

**Gross vs. marginal, and why both are shown:** "gross" energy
(`avg_power × latency`) is what you'd bill if this were the only thing
running on the board. "Marginal" energy (`(avg_power - idle) × latency`)
isolates the *extra* cost this workload adds on top of a board that's
already powered on and idling — arguably the more honest number for "what
does running the fall detector cost" in a system where the board is always
on anyway (as it would be for a room node). By either measure the NPU path
wins, and by a wider margin (7.8×) under the marginal accounting than the
gross one (5.0×), because the NPU's *shorter* latency means less time
paying even the idle overhead.

### Optimization / correctness

| Metric | CPU | NPU |
|---|---|---|
| Precision | FP32 | FP32 |
| Op support | 100% (native ONNX ops, no custom kernels needed) | 100% (0 unsupported ops on HTP v75) |
| Output shape | `(1, 7, 8400)` | `(1, 7, 8400)` |

Both paths ran the *same* unquantized FP32 model — this benchmark isolates
"which compute unit" from "what precision," which is a separate open
question (see `models/fall-detection/README.md`'s "Suggested next steps" —
INT8 hasn't been run on-device on either board yet).

## Caveats — read before citing these numbers elsewhere

1. **N=20 is a reasonable smoke-test sample, not a rigorous benchmark
   suite.** No thermal soak, no steady-state warm-up beyond 3 CPU
   iterations, no repeated trials across reboots. Good enough to establish
   "NPU wins and by roughly how much," not good enough for a paper.
2. **The power sensor measures the whole board's 12V input rail**, not an
   isolated SoC/NPU/CPU power domain. Fan, Wi-Fi radio, USB peripherals,
   background daemons — all of it is baked into every number above. This is
   actually the right metric for "what does this cost the room node," but
   it is *not* a pure silicon-level CPU-vs-NPU power comparison.
3. **The NPU power average is built from only 11 samples** (vs. ~48 for
   CPU) because the whole 20-inference NPU run took 1.27 s at a 100 ms
   sampling interval. Take the NPU power/energy figures as directionally
   right but noisier than the CPU ones.
4. **Synthetic random input, reused across all runs**, not a real camera
   frame — fine for timing/power (compute cost here is shape-driven, not
   content-driven for this architecture) but this benchmark says nothing
   about detection *accuracy* on either path.
5. **CPU threading was left at ONNX Runtime's defaults** (no
   `intra_op_num_threads` tuning). The 604% utilization figure reflects
   whatever ORT chose automatically on this 8-core big.LITTLE part, not a
   deliberately optimized CPU configuration — a tuned CPU config could
   plausibly close some of this gap, though unlikely to erase a 4-6×
   difference.
6. **The idle baseline drifted ~0.22 W between the two measurements taken
   ~10 minutes apart** — use that as a rough sense of the noise floor on
   every power number in this doc.

## Reproducing this

Everything needed is already on the board and in this repo:
- Board: `10.73.51.123`, user `arduino`, password `oelinux@123` (see
  `models/fall-detection/README.md` for the full connection details)
- Artifacts already staged at `/data/local/tmp/quad/models/`: `best.bin`,
  `best.onnx`, `bench_cpu.py`, `input_list_20.txt`
- Re-run either the CPU or NPU command block from the Methodology section
  above verbatim — both are copy-pasteable as-is over the same `plink.exe`
  SSH pattern used throughout this session.
