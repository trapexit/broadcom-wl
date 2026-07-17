# Open Source BCM4352/BCM4360 Driver TODO

Status: planning checklist

Derived from: [`oss_driver_plan.md`](oss_driver_plan.md)

Initial target: one exact BCM4360 PCIe adapter, expected to be a TP-Link Archer
T8E with PCI ID `14e4:43a0`

<!-- IMPLEMENTATION AGENT INSTRUCTION: Commit to Git after every material
change. Keep each commit focused, include the relevant validation result, and
do not accumulate several completed implementation steps in one commit. -->

> **Implementation agent instruction:** Commit to Git after every material
> change. Each commit should contain one coherent change and its relevant
> tests or validation. Do not leave multiple completed implementation steps
> uncommitted or combine unrelated changes.

This checklist converts the research plan into ordered, verifiable work. A
checked task means its evidence has been recorded, not merely that code was
written. Do not pass a phase gate until every listed exit criterion is met.

## Project-wide rules

- [ ] Confirm the actual card identity before allowing experimental code to
  bind; do not rely on a marketing model name alone.
- [ ] Restrict every experimental hardware path to an explicit allowlist of
  PCI subsystem ID, chip revision, D11 core revision, PHY revision, radio
  revision, and board data.
- [ ] Keep RF disabled until the receive-only phase is proven.
- [ ] Require a separate explicit transmit gate after calibration, regulatory,
  containment, and independent-observation checks pass.
- [ ] Never write SPROM, OTP, flash, or other persistent device storage.
- [ ] Do not modify or regenerate `lib/wlc_hybrid.o_shipped`.
- [ ] Do not commit extracted proprietary firmware or unsanitized private
  traces.
- [ ] Load proprietary D11 firmware with `request_firmware()` from a file the
  user extracts from their licensed object.
- [ ] Keep observations, interpretations, confidence levels, and source
  provenance distinct in all register and experiment records.
- [ ] Avoid line-by-line translation of proprietary decompiler output; make
  independent implementations from public documentation, controlled traces,
  and testable state-machine descriptions.
- [ ] Preserve the licenses and attribution of reused Linux, b43-tools,
  Nexmon, and other third-party code.
- [ ] Record the hardware identity, kernel commit, driver commit, firmware
  hash, configuration, scenario, and result for every hardware experiment.
- [ ] Commit to Git after every material implementation change, with a focused
  subject and the applicable test result recorded in the commit or project
  log.

## Capability milestones

- [ ] **Level 0 — safe probe:** bind, identify the device, keep RF disabled,
  and unload repeatedly without error.
- [ ] **Level 1 — firmware alive:** load the correct D11 ucode, start the PSM,
  observe coherent shared memory, and acknowledge interrupts safely.
- [ ] **Level 2 — receive only:** receive beacons and frames on one fixed
  channel with correct metadata and no transmissions.
- [ ] **Level 3 — basic station:** scan, associate, and exchange traffic on an
  open network at conservative legacy rates.
- [ ] **Level 4 — secure station:** run stable WPA2-CCMP station mode with
  software crypto and normal cfg80211 control.
- [ ] **Level 5 — production baseline:** support calibrated 2.4/5 GHz TX,
  regulatory enforcement, HT/VHT, aggregation, reset, and suspend/resume on
  the supported boards.
- [ ] **Level 6 — upstream quality:** land the implementation in `b43` or an
  upstream-approved alternative with reviewable provenance and tests.
- [ ] **Level 7 — fully free stack (optional):** replace the proprietary D11
  ucode with independently implemented open firmware.

Level 5 is the completion threshold for a generally usable host driver. Level
7 is a separate optional firmware project.

## Phase 0 — freeze the target and baseline

### Tasks

- [ ] Prepare a dedicated test host with wired management and reliable remote
  recovery.
- [ ] Install the target adapter without allowing experimental code to bind.
- [ ] Record `lspci -nnvv`, PCI and subsystem IDs, revision, BARs, MSI
  capability, power state, and bound driver.
- [ ] With `wl`, record chip ID/revision, D11 revision, PHY type/revision,
  radio ID/revision, SPROM revision, board revision/flags, MAC address, and
  bands.
- [ ] Establish a known-good `wl` baseline for scan, association, ping,
  throughput, signal reporting, interface reset, suspend/resume, and reload.
- [ ] Hash the exact shipped object, linked `wl.ko`, extracted firmware,
  kernel image, and kernel configuration.
- [ ] Create `docs/hardware/<board-id>.md` containing immutable device identity.
- [ ] Save a sanitized baseline log.
- [ ] Record reproducible kernel and module build instructions.
- [ ] State explicitly which card revision is the initial supported target.

### Gate

- [ ] The card works reliably with `wl`.
- [ ] Exact D11, PHY, radio, and board revisions are known.
- [ ] The host can recover unattended from a kernel crash.
- [ ] If the device is BCM4350 `14e4:43a3`, stop and re-scope around
  `brcmfmac`; do not continue with the BCM4360 SoftMAC assumptions.

## Phase 1 — build the static evidence map

### Tasks

- [ ] Generate a symbol and relocation map for the proprietary object.
- [ ] Record every proprietary-object call site for MMIO, PCI configuration,
  delay, DMA, interrupt, and firmware wrapper functions.
- [ ] Define a machine-readable register database schema with source,
  revision range, and confidence fields.
- [ ] Normalize known D11, BCMA, PCIe, PHY, and radio registers against public
  Linux and b43 sources.
- [ ] Disassemble `d11ucode40.bin` and `d11ucode42.bin` with `b43-dasm`.
- [ ] Annotate probable entry behavior, shared-memory offsets, interrupt
  reasons, and tables without asserting uncertain code/data boundaries.
- [ ] Analyze the relevant Arm RAM image only for supporting upload-sequence,
  object-memory, and component-boundary evidence.
- [ ] Build a shared-memory map with per-entry confidence levels.
- [ ] Maintain an unresolved-question list for controlled experiments.

### Gate

- [ ] Every later wrapper-trace event can be reduced to a BAR/backplane-relative
  offset.
- [ ] Known offsets resolve to named registers and proprietary call sites where
  evidence permits.

## Phase 2 — make `wl` a controlled trace oracle

### Instrumentation tasks

- [ ] Add optional tracing only to the open wrapper sources.
- [ ] Keep tracing disabled by default with one predictable hot-path branch.
- [ ] Select kernel tracepoints or a bounded per-CPU binary ring buffer.
- [ ] Record timestamp/cycle count, CPU/context, operation/width, normalized
  offset, value, proprietary call-site offset, and experiment marker.
- [ ] Add optional DMA map identifiers and lengths without exposing reusable
  private data.
- [ ] Trace MMIO and PCI configuration accesses.
- [ ] Trace BAR/backplane window changes.
- [ ] Trace coherent DMA allocation/free and streaming map/unmap operations.
- [ ] Trace interrupt entry, ownership, mask changes, acknowledgements, and DPC
  scheduling.
- [ ] Trace delays and timers above a configurable threshold.
- [ ] Trace firmware/ucode upload ranges and lifecycle markers.
- [ ] Preserve `readl()`/`writel()` ordering and memory-barrier semantics.
- [ ] Avoid per-access `printk()` and unbounded logging.
- [ ] Mask packet data, keys, MAC addresses, DMA addresses, and kernel pointers
  in any trace intended for publication.
- [ ] Build a userspace binary trace decoder.
- [ ] Build stable-sequence alignment, polling-loop compression, and trace-diff
  tooling.

### Capture tasks

- [ ] Capture repeated probe/remove traces.
- [ ] Capture interface up/down with RF killed.
- [ ] Capture fixed 2.4 GHz and fixed 5 GHz channel changes separately.
- [ ] Capture passive scan.
- [ ] Capture open-network association.
- [ ] Capture WPA2-CCMP association.
- [ ] Capture one small transmitted frame under controlled conditions.
- [ ] Capture sustained RX and sustained TX separately.
- [ ] Capture suspend/resume and explicit reset.
- [ ] Align captures on explicit lifecycle markers and change one experimental
  variable at a time.

### Gate

- [ ] Repeated traces of the same scenario are structurally consistent.
- [ ] Disabled tracing overhead is measured and negligible.
- [ ] Enabled tracing does not alter behavior beyond a documented tolerance.
- [ ] Reset, upload, channel setup, IRQ enable, and first TX/RX sequences can be
  isolated.
- [ ] If important MMIO bypasses the wrapper boundary, add a narrowly scoped
  observation method before interpreting incomplete traces.

## Phase 3 — implement a safe read-only probe

### Tasks

- [ ] Start from a current upstream kernel rather than the archived Linux-facing
  code in this repository.
- [ ] Create the small out-of-tree `b43ac` research module.
- [ ] Match only the confirmed PCI subsystem, BCMA chip, and D11 revision.
- [ ] Enumerate BCMA cores without resetting D11 or enabling RF.
- [ ] Read and report identity, SPROM, core, PHY, and radio information.
- [ ] Expose one structured debugfs or tracefs state snapshot.
- [ ] Keep core reset and firmware upload opt-in and disabled by default.
- [ ] Implement complete unwind paths for every probe failure.
- [ ] Add fault injection for bind, initialization, and teardown failures.
- [ ] Test bind/unbind, load/unload, reboot, and recovery paths.

### Gate — Level 0

- [ ] Complete 100 consecutive bind/unbind cycles without warnings or leaks.
- [ ] Preserve the ability to bind `wl` afterward.
- [ ] Reject unknown revisions before any hardware write.
- [ ] Verify that RF, DMA, and interrupts remain disabled.

## Phase 4 — create the firmware pipeline

### Tasks

- [ ] Document the current b43 firmware-container header and upload byte order.
- [ ] Confirm the target D11 revision before selecting `ucode40` or `ucode42`.
- [ ] Implement a strict converter from the exact extracted payload to the
  selected `b43/*.fw` container.
- [ ] Validate input length, instruction-record form, source-object hash, and
  output hash; reject unknown inputs.
- [ ] Compare output with b43-fwcutter conventions.
- [ ] Verify `b43-dasm` round trips where meaningful.
- [ ] Add tests for truncation, malformed headers, wrong revisions, unexpected
  hashes, and seven/eight-byte records.
- [ ] Determine whether revision-specific initvals are also required.
- [ ] Keep initvals distinct from ucode.
- [ ] Load through `request_firmware()` without compiling payload bytes into
  GPL source.
- [ ] Upload while the PSM is held stopped and verify by readback or another
  reliable method.

### Gate

- [ ] A user can reproduce byte-identical firmware from their licensed object.
- [ ] All malformed or unknown inputs fail cleanly.
- [ ] The stopped-core upload is repeatable and verified.
- [ ] If the actual D11 revision is neither 40 nor 42, stop; do not select
  firmware based only on the extracted symbol name.

## Phase 5 — start D11 without RF

### Tasks

- [ ] Reproduce the minimum BCMA clock and D11 reset sequence.
- [ ] Establish D11 object-memory and shared-memory access.
- [ ] Upload ucode and initialize only mandatory shared memory.
- [ ] Start the PSM while RF remains disabled.
- [ ] Identify a revision word, heartbeat, or stable shared-memory proof of
  execution.
- [ ] Implement interrupt masks and acknowledgements before enabling IRQs.
- [ ] Implement watchdog recovery that masks IRQs, stops DMA, halts PSM, and
  resets the core without persistent writes.
- [ ] Test cold boot, warm reset, reload, firmware rejection, unexpected IRQ,
  and stalled-PSM recovery.

### Gate — Level 1

- [ ] Firmware-alive behavior is repeatable across all reset paths.
- [ ] No RF path is enabled.
- [ ] IRQ and PSM failures recover within bounded time without a storm or hang.
- [ ] If the firmware requires an unanticipated Arm/RPC control plane, stop and
  reassess the SoftMAC architecture.

## Phase 6 — implement AC-PHY receive-only operation

### Callback audit

- [ ] Audit every `b43_phy_operations` callback used by common code.
- [ ] Implement or explicitly reject allocation/release, prepare/init/exit,
  reinit, RF-kill, PHY/radio access, channel control, width, antennas/chains,
  TX-power handling, maintenance, and calibration hooks.
- [ ] Replace unsafe null callbacks with controlled errors.

### Bring-up tasks

- [ ] Classify trace writes by common, chip, PHY, radio, band, channel, and
  calibration scope.
- [ ] Reproduce only the invariant initialization required for one 20 MHz
  receive channel.
- [ ] Read back stage results and compare them with known-good `wl` state.
- [ ] Keep all TX queues stopped and power amplifiers disabled.
- [ ] Implement RX rings and descriptor parsing.
- [ ] Report conservative, understood metadata to `mac80211`.
- [ ] Validate FCS disposition, channel, rate, signal, and timestamp metadata.
- [ ] Run ten-minute and overnight receive-only tests.
- [ ] Use an independent monitor receiver to check for unintended emission.

### Gate — Level 2

- [ ] Receive valid beacons/frames on one fixed 20 MHz channel.
- [ ] Independently confirm that the target transmitted no frames.
- [ ] Observe no DMA leak, ring stall, IRQ storm, or memory corruption.

## Phase 7 — add calibrated, constrained transmit

### Mandatory preconditions

- [ ] Decode exact-board SPROM/OTP calibration fields.
- [ ] Understand per-band antenna and chain configuration.
- [ ] Enforce a conservative hardware-independent maximum power.
- [ ] Intersect board limits with cfg80211 rules so userspace can only reduce
  permitted operation.
- [ ] Reject unsupported channel/bandwidth combinations.
- [ ] Establish RF shielding or conducted attenuation.
- [ ] Operate an independent monitor/measurement receiver.

### Tasks

- [ ] Add a second, explicit transmit-enable gate.
- [ ] Implement one low legacy OFDM rate on one fixed allowed channel.
- [ ] Construct one TX descriptor/template with normal queues stopped.
- [ ] Verify center frequency, bandwidth, bytes, rate, and relative power
  independently.
- [ ] Parse completion and ACK status.
- [ ] Add queue stop/wake, timeouts, DMA cleanup, and retry handling.
- [ ] Expand one dimension at a time: rate, channel, band, spatial chain, then
  bandwidth.

### Gate

- [ ] Prove that transmission cannot occur outside the selected regulatory
  channel.
- [ ] Bound power by both board calibration and cfg80211.
- [ ] Complete successful and failed TX without leaked mappings or stuck queues.
- [ ] Do not continue if calibration, regulatory intersection, containment, or
  independent observation is missing.

## Phase 8 — integrate normal station operation

### Tasks

- [ ] Implement the minimum station and monitor `ieee80211_ops` lifecycle.
- [ ] Implement software scan before considering hardware scan.
- [ ] Associate to an open AP using software rate control.
- [ ] Exchange conservative legacy-rate traffic.
- [ ] Enable software CCMP through `mac80211`.
- [ ] Validate disassociation, roaming, beacon loss, queue recovery, and AP
  restart.
- [ ] Add only signal/statistics fields with understood units and update rules.
- [ ] Verify headers, sequence numbers, ACK behavior, and crypto boundaries in
  packet captures.

### Gate — Levels 3 and 4

- [ ] Open and WPA2-CCMP station operation work through standard nl80211 tools.
- [ ] Repeated association/disassociation does not require module reload.
- [ ] No driver-private userspace control is required.

## Phase 9 — add HT and VHT incrementally

- [ ] Stabilize legacy operation on 2.4 GHz and 5 GHz.
- [ ] Add one spatial stream at 20 MHz.
- [ ] Add and test MCS values incrementally.
- [ ] Add additional RX/TX chains one at a time.
- [ ] Add A-MPDU receive.
- [ ] Add A-MPDU transmit.
- [ ] Add 40 MHz operation.
- [ ] Advertise only tested VHT capabilities.
- [ ] Add 80 MHz operation last.
- [ ] Test each feature with multiple AP implementations and an independent
  sniffer.

## Phase 10 — harden lifecycle and recovery

- [ ] Test interface up/down and RF kill.
- [ ] Test repeated scan cancellation.
- [ ] Inject association failures at each stage.
- [ ] Inject DMA allocation and mapping failures.
- [ ] Test firmware rejection and PSM stall.
- [ ] Test interrupt storms and lost interrupts.
- [ ] Test TX timeout and RX ring starvation.
- [ ] Test PCI power-state transitions.
- [ ] Test suspend/resume and supported hibernation paths.
- [ ] Test module reload after every major failure class.
- [ ] Test warm and cold reboot.
- [ ] Add safe debug counters for recovery, rings, IRQ reasons, PSM state, and
  channel transitions.
- [ ] Verify debug facilities expose no keys, frames, kernel pointers, or
  unrestricted register writes.

## Phase 11 — broaden hardware coverage

- [ ] Reach Level 5 on the first supported card before adding hardware.
- [ ] Test a second sample of the same subsystem revision.
- [ ] Treat another BCM4360 board as a new calibrated variant.
- [ ] Record that variant's SPROM, radio, PHY, D11, and board differences.
- [ ] Add BCM4352 only after documenting its complete revision differences.
- [ ] Keep all unrecorded identities rejected by default.
- [ ] Key compatibility on full hardware identity, not marketing chip name.

## Phase 12 — upstream the host driver

### Coordination

- [ ] Contact `linux-wireless` after safe-probe and firmware-format work, before
  building a large permanent fork.
- [ ] Ask whether maintainers prefer completing `b43` AC-PHY support or a
  separate driver sharing b43 helpers.
- [ ] Record the agreed upstream shape and adjust the local module accordingly.

### Proposed patch sequence

- [ ] Submit nonfunctional register definitions and documentation.
- [ ] Submit firmware parsing tests and revision handling.
- [ ] Submit safe AC-PHY callback completion with explicit errors.
- [ ] Submit D11 core-revision fixes independent of AC-PHY.
- [ ] Submit read-only AC-PHY initialization.
- [ ] Submit receive support.
- [ ] Submit calibrated transmit support.
- [ ] Submit station support.
- [ ] Submit HT/VHT features.

### Validation and gate — Level 6

- [ ] Run applicable kernel builds and `checkpatch.pl`.
- [ ] Run sparse and Smatch where available.
- [ ] Run lockdep, KASAN, and DMA API debugging.
- [ ] Run relevant `mac80211_hwsim` tests.
- [ ] Include exact hardware commands, identities, and results with patches.
- [ ] Keep each upstream patch independently reviewable and bisectable.
- [ ] Obtain upstream acceptance in `b43` or an approved alternative.

## Phase 13 — optional open D11 firmware

Start this phase only after the host driver is stable with known proprietary
firmware; otherwise host and firmware failures cannot be separated.

- [ ] Specify revision-42 D11 instruction encoding and upload format using
  b43-tools and controlled experiments.
- [ ] Specify the host-driver/PSM shared-memory ABI.
- [ ] Implement firmware that boots with RF disabled and reports version and
  heartbeat.
- [ ] Implement safe stop and recovery.
- [ ] Add receive events and descriptor delivery.
- [ ] Add ACK timing and one constrained transmit path.
- [ ] Add retransmission, filtering, timing, power save, aggregation,
  coexistence, and crypto coordination incrementally.
- [ ] Use distinct filenames for proprietary and open firmware.
- [ ] Compare both implementations under identical experiments.
- [ ] Treat OpenFWWF as older prior art, not as an unchanged revision-42 model.

### Gate — Level 7

- [ ] The supported host driver operates with independently implemented D11
  firmware without relying on extracted proprietary payloads.

## Recurring test checklist

### Unit and parser tests

- [ ] Test firmware header, length, revision, and hash validation.
- [ ] Test seven-byte and eight-byte D11 record conversion.
- [ ] Test endian and register-field helpers.
- [ ] Test SPROM decoding with sanitized fixtures.
- [ ] Test TX/RX descriptor packing and unpacking.
- [ ] Test channel and bandwidth validation.
- [ ] Test board/regulatory power-limit intersection.
- [ ] Test trace alignment and polling-loop compression.
- [ ] Use KUnit for kernel-only helpers and userspace tests for extraction,
  conversion, trace decoding, and register tooling.

### Hardware matrix

- [ ] Cover cold boot, warm boot, and module reload.
- [ ] Cover 2.4 GHz and 5 GHz where enabled.
- [ ] Cover 20 MHz first; add 40/80 MHz only with their feature phases.
- [ ] Cover open and WPA2-CCMP; add WPA3 only if supported and tested.
- [ ] Cover RX-only, TX-only, bidirectional, small, and large traffic.
- [ ] Cover scan, association, roam, disconnect, RF kill, and suspend/resume.
- [ ] Cover AP loss, firmware stall, timeout, and allocation failure.
- [ ] Test the development kernel and maintained LTS kernels.
- [ ] Record card, firmware, kernel, compiler, driver commit, configuration,
  AP, channel, and duration for every result.

### Regression artifacts

- [ ] Commit sanitized firmware-container headers without payload bytes.
- [ ] Commit descriptor fixtures with addresses and frame data masked.
- [ ] Commit small sanitized register-trace transitions.
- [ ] Commit expected trace-decoder summaries.
- [ ] Commit sanitized SPROM layouts.
- [ ] Store large/private captures outside Git and reference them by hash.

## Immediate ordered backlog

Complete these in order; entries 1–7 do not require an experimental driver to
control the radio, while entries 8 onward require target hardware and a
recoverable laboratory host.

- [ ] **1.** Hardware-manifest template and read-only collection script.
- [ ] **2.** Experiment manifest containing all relevant hashes and versions.
- [ ] **3.** Register database schema with source and confidence fields.
- [ ] **4.** Optional OSL tracepoints for MMIO, PCI, DMA, IRQ, and DPC.
- [ ] **5.** Binary trace decoder and stable-sequence differ.
- [ ] **6.** Baseline `wl` captures for probe, up/down, and fixed-channel
  changes.
- [ ] **7.** Strict `d11ucode42.bin` to b43-container converter, subject to
  confirmed D11 revision.
- [ ] **8.** Current-kernel read-only `b43ac` BCMA probe for one exact device.
- [ ] **9.** Safe firmware upload with the PSM held stopped.
- [ ] **10.** PSM heartbeat, interrupt-mask, and bounded recovery experiment.
- [ ] **11.** AC-PHY callback audit with controlled errors replacing unsafe
  missing operations.
- [ ] **12.** One-channel receive-only implementation.

## Final completion review

- [ ] Reconcile all checked items with logs, tests, and Git commits.
- [ ] Confirm all supported identities are explicit and unknown devices fail
  safely.
- [ ] Confirm no proprietary payload, sensitive capture, or private identifier
  is committed.
- [ ] Confirm regulatory and board limits cannot be bypassed.
- [ ] Confirm Level 5 is repeatable before calling the host driver generally
  usable.
- [ ] Update [`oss_driver_plan.md`](oss_driver_plan.md) when evidence changes
  the architecture, safety gates, or phase ordering.
