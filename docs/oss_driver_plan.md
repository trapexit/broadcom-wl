# Plan for an Open Source BCM4352/BCM4360 Linux Driver

Status: proposed research and implementation plan  
Prepared: 2026-07-17

## Executive decision

The recommended target is an open source Linux SoftMAC driver for one specific
BCM4360 PCIe adapter first, expected to be the TP-Link Archer T8E identified by
PCI ID `14e4:43a0`. BCM4352 support should follow only after the exact first
card works. The hardware identity must be confirmed on the development machine
before any code binds to the device.

The shortest credible route is:

1. use a small out-of-tree `b43ac` research module for safe probing and rapid
   experimentation;
2. use the working proprietary `wl` module as a black-box trace oracle;
3. reuse Linux's BCMA, `mac80211`, cfg80211, DMA, and firmware-loading
   infrastructure;
4. initially load user-extracted Broadcom D11 microcode;
5. move successful support into the existing upstream `b43` driver; and
6. treat replacement open D11 microcode as a later, independent project.

This produces an open source host driver without requiring the radio firmware
to be open on day one. A completely free stack requires both the host driver
and independently implemented D11 PSM microcode. Replacing the Cortex-R4
FullMAC firmware used by BCM4350-class devices is out of scope for the initial
project.

## Why this route is preferred

Current Linux already contains most of the generic machinery required by this
hardware:

- `bcma` enumerates the Broadcom backplane and its D11 core;
- `mac80211` supplies the SoftMAC 802.11 state machine;
- `b43` contains D11 core control, firmware upload, shared-memory access,
  template RAM, DMA/PIO, TX/RX, interrupt, and debug infrastructure;
- current `b43` declares firmware names `ucode40.fw` and `ucode42.fw` and
  matches BCMA D11 core revisions `0x28` and `0x2a`; and
- `b43` already contains an AC-PHY operations skeleton for BCM4352 and BCM4360.

The AC-PHY option remains hidden behind `BROKEN`, and upstream explicitly warns
that it crashes. Its operation table implements only a few register-access and
allocation helpers; critical initialization and channel-control operations are
absent. This makes the missing scope visible and gives the project a natural
upstream destination.

Creating a permanent standalone driver would duplicate mature, difficult code
from `b43`. A standalone research module is still useful before radio bring-up
because it can enforce strict safety rules and expose concise diagnostics. It
should be considered a laboratory vehicle, not the final architecture.

## Known local evidence

The extraction and architecture analysis in
[`firmware_architecture.md`](firmware_architecture.md) establishes two relevant
execution environments:

- `dlarray_4350pci.bin` and `dlarray_4352pci.bin` are little-endian Armv7-R
  Thumb-2 RAM firmware, with Cortex-R4 the high-confidence core identification;
- `d11ucode*` and `d11aeswakeucode*` are programs for Broadcom's proprietary D11
  Programmable State Machine, not Arm code and not conventional DSP code; and
- `d11ucode40.bin` and `d11ucode42.bin` are present in the extracted set and
  correspond by naming convention to D11 core revisions already recognized by
  current `b43`.

The shipped proprietary object is also unusually useful as a trace oracle.
As documented in [`wlc_hybrid_info.txt`](wlc_hybrid_info.txt), all 85 unresolved
imports cross an inspectable wrapper boundary. Hardware and kernel interaction
passes through functions including:

- `osl_readb`, `osl_readw`, `osl_readl`;
- `osl_writeb`, `osl_writew`, `osl_writel`;
- `osl_pci_read_config`, `osl_pci_write_config`;
- `osl_dma_alloc_consistent`, `osl_dma_map`, and their release operations;
- interrupt and DPC entry points in `wl_linux.c`; and
- timers, packet allocation, and interface lifecycle functions.

There are hundreds of static references to the MMIO wrapper functions. The
known-good module can therefore produce a detailed register trace without
modifying `lib/wlc_hybrid.o_shipped`.

## Definitions of success

The project should report progress using explicit capability levels:

| Level | Definition |
| --- | --- |
| 0: safe probe | The driver binds, identifies the device, keeps RF disabled, and repeatedly unloads without error. |
| 1: firmware alive | The correct D11 ucode loads, the PSM starts, shared-memory state is coherent, and interrupts can be acknowledged. |
| 2: receive only | One fixed channel can receive beacons and frames with correct metadata without transmitting. |
| 3: basic station | The device scans, associates, and exchanges traffic on an open network using conservative legacy rates. |
| 4: secure station | WPA2-CCMP station mode is stable with software crypto and normal cfg80211 control. |
| 5: production baseline | 2.4 and 5 GHz, calibrated transmit power, regulatory enforcement, HT/VHT, aggregation, reset, and suspend/resume work on supported boards. |
| 6: upstream quality | The implementation is accepted into `b43` or an upstream-approved replacement, with reviewable provenance and tests. |
| 7: fully free stack | Independently implemented open D11 microcode replaces the extracted proprietary payload. |

Level 5, not merely a successful association, is the completion threshold for
a generally usable driver. Level 7 is an optional follow-on project.

## Scope

### Initial goals

- Support exactly one BCM4360 PCIe card and revision.
- Use BCMA rather than duplicating Broadcom backplane enumeration.
- Integrate with `mac80211` and cfg80211 rather than expose private wireless
  ioctls.
- Load D11 firmware with `request_firmware()`.
- Preserve SPROM/OTP contents and derive board, calibration, and regulatory
  data without writing nonvolatile storage.
- Begin with RX-only operation on a single fixed channel.
- Implement station and monitor modes before considering other interface types.
- Make every hardware-changing step traceable and independently disableable.
- Keep the final source suitable for review on `linux-wireless`.

### Initial non-goals

- BCM4350 FullMAC support through replacement Cortex-R4 firmware.
- AP, P2P, mesh, WoWLAN, Bluetooth coexistence, or multi-interface operation.
- Hardware crypto during initial association work.
- 40 or 80 MHz operation before stable 20 MHz RX and TX.
- Maximum throughput before correctness, power control, and recovery.
- Redistribution of Broadcom object files or extracted firmware.
- Writing SPROM, OTP, flash, or other persistent device storage.

## Driver architecture

### Final upstream shape

The expected upstream implementation is an extension of `b43`:

```text
userspace: iw / wpa_supplicant / NetworkManager
                 |
             nl80211
                 |
       cfg80211 + mac80211
                 |
        b43 common D11 driver
          |             |
    AC-PHY/radio     DMA/PIO, IRQ,
      support        TX/RX, SHM
          \             /
                BCMA
                 |
          BCM4352/BCM4360
                 |
            D11 PSM ucode
```

New code should live behind the existing `b43_phy_operations` abstraction and
use common D11 paths wherever the core revision permits. Core-revision-specific
changes must be separated from AC-PHY changes so each can be reviewed and
tested independently.

### Research-module shape

Before modifying a production driver, create an out-of-tree laboratory module
with a deliberately small surface:

- a BCMA device match restricted to the confirmed chip, core, and PCI
  subsystem IDs;
- read-only identity, SPROM, core, PHY, and radio reporting;
- opt-in core reset and firmware upload, disabled by default;
- opt-in fixed-channel RX, disabled by default;
- no normal network interface until the RX milestone; and
- a debugfs state snapshot and trace marker interface.

The module must refuse unknown revisions. A module parameter such as
`unsafe_enable=1` may gate hardware-changing experiments, but transmit must
require a separate, more explicit gate after power-control review.

### Internal components

Keep the experimental code divided by responsibility:

| Component | Responsibility |
| --- | --- |
| `bus` | BCMA binding, PCI identity, BAR/backplane windows, device lifetime |
| `core` | D11 reset, clocks, object memory, shared memory, template RAM |
| `firmware` | Firmware selection, validation, upload, PSM start/stop |
| `phy_ac` | AC-PHY register access, initialization, channel configuration |
| `radio` | Radio revision handling, calibration, RF enable/disable |
| `dma` | Descriptor formats, rings, coherent allocations, mapping and recovery |
| `irq` | Interrupt masks, acknowledge order, bottom-half scheduling |
| `tx` and `rx` | Frame descriptors, status parsing, queueing, radiotap metadata |
| `mac80211` | `ieee80211_ops`, capabilities, channel and interface lifecycle |
| `trace` | Structured state transitions and register/DMA event capture |

Do not mix inferred constants, register definitions, and high-level policy in
one file. Register definitions should record their evidence source and known
revision range.

## Provenance and clean implementation policy

The project should be designed for later upstream review from its first commit.
This is an engineering provenance policy, not legal advice.

1. Do not modify or regenerate `lib/wlc_hybrid.o_shipped`.
2. Do not commit extracted proprietary firmware. Commit extraction and format
   conversion tools, expected hashes, and instructions requiring the user to
   supply their own licensed object.
3. Separate facts observed from hardware from interpretations. Every register
   entry should state whether it came from public source, static analysis,
   trace comparison, or experiment.
4. Do not translate proprietary decompiler output line by line into driver
   source. Implement independently from documented behavior, controlled traces,
   and testable state-machine descriptions.
5. Keep raw trace captures outside Git when they contain packets, keys, MAC
   addresses, or other private data. Store sanitized fixtures for tests.
6. Preserve the licenses and attribution of any reused `b43`, `brcmsmac`, BCMA,
   Nexmon, or b43-tools code.
7. Maintain an experiment log with object hash, card identity, kernel commit,
   driver commit, firmware hash, scenario, and result.

## Laboratory and hardware requirements

The current development host does not expose a Broadcom PCI device. Live work
requires a dedicated test environment containing:

- at least two examples of the same target adapter revision;
- a wired management interface independent of the target device;
- serial console, netconsole, or reliable remote reboot capability;
- a kernel with debug symbols and a reproducible build configuration;
- a controllable access point supporting fixed channel, bandwidth, security,
  and transmit power;
- a second known-good monitor receiver for independent packet observation;
- RF shielding or conducted attenuation for early transmit work; and
- storage of known-good kernels so a crashing module cannot strand the host.

Useful kernel diagnostics include KASAN, UBSAN, lockdep, DMA API debugging,
kmemleak, dynamic debug, ftrace, and tracepoints. Enable them selectively;
instrumentation changes timing and can hide or create failures.

## Phase 0: freeze the target and establish a baseline

### Work

1. Install the target card without allowing experimental code to bind.
2. Record `lspci -nnvv`, subsystem IDs, PCI revision, BARs, MSI capability,
   power state, and the driver currently bound.
3. With `wl`, record chip ID, chip revision, D11 core revision, PHY type and
   revision, radio ID and revision, SPROM revision, board revision, board flags,
   MAC address, and supported bands.
4. Record a known-good functional baseline: scan, association, ping, throughput,
   signal reporting, interface reset, suspend/resume, and module reload.
5. Hash the exact `wlc_hybrid.o_shipped`, final `wl.ko`, extracted firmware,
   kernel image, and kernel configuration used for all later traces.

### Deliverables

- `docs/hardware/<board-id>.md` with immutable device identity;
- a sanitized baseline log;
- a reproducible kernel and module build recipe; and
- an explicit statement of which card is the initial supported target.

### Exit criteria

The card works reliably with `wl`, its exact D11/PHY/radio revisions are known,
and the test host can recover unattended from a kernel crash.

## Phase 1: build the static evidence map

### Work

1. Generate a symbol and relocation map for the proprietary object.
2. Record the offset of every call site to MMIO, PCI configuration, delay, DMA,
   interrupt, and firmware-related wrapper functions.
3. Normalize all known D11, BCMA, PCIe, PHY, and radio registers against public
   kernel headers and b43 sources.
4. Disassemble `d11ucode40.bin` and `d11ucode42.bin` with `b43-dasm` and record
   entry behavior, shared-memory offsets, interrupt reasons, and recognizable
   tables without claiming false code/data boundaries.
5. Analyze the relevant Arm RAM image only as supporting evidence for upload
   sequences, D11 object-memory access, and component boundaries.

### Deliverables

- a machine-readable register database;
- a proprietary-object call-site map keyed by section-relative offset;
- annotated D11 disassembly workspaces;
- a shared-memory map with confidence levels; and
- a list of unresolved questions to answer through controlled traces.

### Exit criteria

Every event in a later wrapper trace can be reduced to a BAR-relative register
offset and, where possible, a named register and proprietary call site.

## Phase 2: turn `wl` into a controlled trace oracle

### Instrumentation design

Add optional instrumentation only to the open wrapper sources. It must be off
by default and impose one predictable branch on the hot path when disabled.

Trace records should contain:

```text
monotonic timestamp or cycle counter
CPU and execution context
operation class and access width
BAR-relative or backplane-relative offset
value read or written
call-site offset inside wlc_hybrid.o_shipped
current experiment marker
optional DMA map identifier and length
```

Use kernel tracepoints or a bounded per-CPU binary ring buffer. Do not emit an
unbounded `printk()` for each MMIO access. Reads must be logged after the actual
read; writes should record both value and address without changing ordering.
Tracing must preserve `readl()`/`writel()` semantics and memory barriers.

Track at least:

- MMIO and PCI configuration accesses;
- BAR/backplane window changes;
- coherent DMA allocation and free;
- streaming DMA map/unmap, direction, length, and returned address;
- interrupt entry, ownership result, mask changes, and DPC scheduling;
- delays and timers above a configurable threshold;
- firmware and ucode upload ranges; and
- lifecycle markers such as probe, up, scan, channel change, associate, TX,
  down, suspend, and resume.

Do not record general packet payloads or keys. Descriptor snapshots should mask
DMA addresses when captures will be published.

### Controlled scenarios

Capture several repetitions of each operation while changing one variable:

1. probe and remove;
2. interface up and down with RF killed;
3. fixed 2.4 GHz channel selection;
4. fixed 5 GHz channel selection;
5. passive scan;
6. association to an open test AP;
7. association using WPA2-CCMP;
8. one small transmitted frame;
9. sustained receive and transmit separately;
10. suspend/resume and explicit device reset.

Align traces on lifecycle markers, remove polling-loop repetitions, and compare
stable write sequences before interpreting read-dependent branches.

### Exit criteria

- Repeated traces of the same scenario are structurally consistent.
- The disabled path has measured negligible overhead.
- The enabled path does not change association or throughput beyond documented
  tolerance.
- Firmware upload, reset, channel setup, interrupt enable, and first TX/RX
  sequences can be isolated from the complete trace.

## Phase 3: implement a safe read-only probe

### Work

1. Base the laboratory module on the current upstream kernel, not the archived
   kernel-facing code in this repository.
2. Match only the exact confirmed PCI subsystem, BCMA chip, and D11 core
   revision.
3. Enumerate BCMA cores and read identity and SPROM information without
   resetting the D11 core or enabling RF.
4. Expose one structured state snapshot through debugfs or tracefs.
5. Implement complete unwind paths for every probe failure.
6. Exercise bind/unbind, module load/unload, reboot, and surprise failure paths
   with fault injection.

### Exit criteria

- One hundred consecutive bind/unbind cycles complete without warnings,
  leaks, stuck PCI power state, or loss of the ability to bind `wl` afterward.
- Unknown revisions are rejected before any hardware write.
- RF remains disabled and no DMA or interrupt is enabled.

## Phase 4: create a reproducible firmware pipeline

### Work

1. Document the current b43 firmware container header and upload byte order.
2. Add a converter from the exact extracted D11 form to `b43/ucode42.fw` or the
   firmware name selected by the confirmed D11 core revision.
3. Validate input length, instruction-record structure, source object hash, and
   output hash. Refuse unknown input.
4. Compare converter output with b43-fwcutter conventions and `b43-dasm` round
   trips.
5. Load with `request_firmware()`; never compile the proprietary bytes into the
   GPL module.
6. Determine whether the target also needs extracted initvals, and keep
   revision-specific initvals separate from ucode.

### Exit criteria

- A user can reproduce the identical firmware file from the licensed object.
- The loader rejects truncation, incorrect revision, malformed header, and
  unexpected hashes cleanly.
- Firmware is uploaded and read back or otherwise verified while the PSM is
  held stopped.

## Phase 5: bring up the D11 core without RF

### Work

1. Reproduce the minimum BCMA clock and reset sequence.
2. Establish D11 object-memory and shared-memory access.
3. Upload ucode, initialize only mandatory shared memory, and start the PSM.
4. Identify a firmware revision word, heartbeat, or stable shared-memory state
   proving that the PSM is executing.
5. Implement interrupt masking and acknowledgement before enabling an IRQ.
6. Add watchdog recovery that stops DMA, masks interrupts, halts the PSM, and
   resets the core without touching persistent storage.

### Exit criteria

- Level 1 is met repeatedly after cold boot, warm reset, module reload, and
  deliberate firmware rejection.
- No RF path is enabled.
- An unexpected interrupt or stalled PSM produces a bounded recovery instead
  of an interrupt storm or system hang.

## Phase 6: implement AC-PHY receive-only operation

### Required PHY operations

The current AC-PHY skeleton must be audited against the complete
`b43_phy_operations` contract. At minimum, safely implement or explicitly reject:

- allocation and release;
- prepare, initialize, exit, and full reinitialize;
- analog and software RF-kill control;
- PHY and radio register access;
- default channel selection and channel switching;
- channel-width handling;
- antenna and chain selection;
- transmit-power calculation and adjustment; and
- periodic maintenance and calibration hooks.

Stubbed callbacks must return controlled errors. They must never be absent when
common `b43` code calls them unconditionally.

### Method

1. Derive reset and base initialization from stable `wl` traces.
2. Classify writes as common, chip-specific, PHY-revision-specific,
   radio-revision-specific, band-specific, channel-specific, or calibration
   results.
3. Reproduce only the invariant minimum required for one channel.
4. Read back registers and compare with the known-good driver after each stage.
5. Keep transmit queues stopped and power amplifiers disabled.
6. Parse RX descriptors and report frames to `mac80211` with conservative,
   explicitly known metadata.

### Exit criteria

- Level 2 is met on one 20 MHz channel.
- An independent monitor receiver confirms that the target emitted no frames.
- Received beacons have correct FCS disposition, channel, rate, signal, and
  timestamp metadata where supported.
- Ten-minute and overnight receive tests show no DMA leak, descriptor stall,
  interrupt storm, or memory corruption.

## Phase 7: add calibrated, constrained transmit

Transmit is a separate safety gate. Do not enable it merely because receive
works.

### Preconditions

- SPROM/OTP calibration fields are decoded for the exact board.
- Per-band antenna and chain configuration is understood.
- A conservative maximum power can be enforced independently of userspace.
- cfg80211 regulatory restrictions can only reduce, never expand, the board
  limits.
- Channel and bandwidth validation rejects unsupported combinations.
- Testing takes place through shielding or conducted attenuation.

### Work

1. Implement one low legacy OFDM rate on one fixed channel.
2. Construct one TX descriptor and template while all normal queues remain
   stopped.
3. Verify emitted center frequency, bandwidth, frame bytes, rate, and relative
   power with independent equipment.
4. Parse TX completion and ACK status.
5. Add queue stop/wake, timeout, DMA cleanup, and retry handling.
6. Expand one dimension at a time: rates, channels, band, spatial chains, then
   bandwidth.

### Exit criteria

- No transmission can occur outside the selected regulatory channel.
- Device power is bounded by both board calibration and cfg80211.
- Failed and successful TX complete without leaked mappings or stuck queues.
- Level 3 can be attempted without private ioctls or bypassing `mac80211`.

## Phase 8: integrate normal station operation

### Work

1. Implement the minimum `ieee80211_ops` lifecycle required for station and
   monitor modes.
2. Support software scan first; consider hardware scan only after normal
   channel switching is stable.
3. Associate to an open AP using software rate control.
4. Enable software CCMP through `mac80211`; defer hardware key tables.
5. Validate disassociation, roam, beacon loss, queue recovery, and AP restart.
6. Add signal reporting and statistics only when their units and update rules
   are understood.

### Exit criteria

- Levels 3 and 4 are met without driver-private userspace tools.
- Repeated association and disassociation do not require reloading the module.
- Packet capture confirms correct 802.11 headers, sequence numbers, ACK
  behavior, and encryption boundaries.

## Phase 9: add HT and VHT features incrementally

Feature order should be conservative:

1. stable legacy operation on 2.4 GHz and 5 GHz;
2. one spatial stream at 20 MHz;
3. additional MCS values;
4. multiple receive and transmit chains;
5. A-MPDU receive, then transmit;
6. 40 MHz operation;
7. VHT capability advertisement; and
8. 80 MHz operation.

Advertise only capabilities exercised by the driver. Incorrect VHT capability
bits can cause failures before association and are not harmless placeholders.
Each added feature needs interoperability tests against multiple access-point
implementations and an independent sniffer.

## Phase 10: harden lifecycle and recovery

Test all state transitions rather than only steady traffic:

- interface up/down and RF kill;
- repeated scan cancellation;
- association failure at each stage;
- DMA allocation and mapping failure;
- firmware rejection and PSM stall;
- interrupt storm and lost interrupt;
- TX timeout and RX ring starvation;
- PCI power-state change;
- suspend/resume and hibernate where applicable;
- module reload after failure; and
- warm and cold reboot.

Add debug counters for recovery reasons, ring state, interrupt reasons, PSM
state, and last channel transition. Debug facilities must not expose keys,
packet contents, kernel pointers, or unrestricted register writes.

## Phase 11: broaden hardware coverage

Only after Level 5 on the first card:

1. test a second sample of the same subsystem revision;
2. test another BCM4360 board while treating its SPROM and radio data as a new
   variant;
3. add BCM4352 only after recording its exact chip, D11, PHY, radio, and board
   differences; and
4. reject all other IDs until each has an explicit initialization and
   calibration record.

Never use a marketing chip name as the compatibility key. PCI subsystem,
backplane chip revision, D11 core revision, PHY revision, radio revision, and
board data all participate in the support decision.

## Phase 12: upstream the host driver

Contact `linux-wireless` maintainers early, after the safe-probe and firmware
format work but before accumulating a large permanent fork. Ask whether the
preferred submission is completion of `b43` AC-PHY support or a separate
driver sharing selected b43 helpers.

Prepare a reviewable patch sequence such as:

1. nonfunctional register definitions and documentation;
2. firmware parsing tests and revision handling;
3. safe AC-PHY callback completion returning explicit errors;
4. D11 core-revision fixes independent of AC-PHY;
5. read-only AC-PHY initialization;
6. receive support;
7. calibrated transmit support;
8. station support; and
9. HT/VHT features.

Before submission, run normal kernel build tests plus `checkpatch.pl`, sparse,
Smatch where available, lockdep, KASAN, DMA API debugging, and relevant
`mac80211_hwsim` tests. Hardware-specific behavior cannot be proven by
`mac80211_hwsim`, so include exact on-device commands and results in every
cover letter.

## Phase 13: optional open D11 firmware

This begins only after the host driver is stable with known firmware. It is a
separate project because firmware and driver failures otherwise become
indistinguishable.

### Work

1. Specify the D11 revision-42 instruction encoding and object-memory upload
   format using `b43-dasm`, `b43-asm`, and controlled instruction experiments.
2. Specify the driver/PSM shared-memory ABI used by the new host driver.
3. Implement a minimal firmware that boots, exposes a version and heartbeat,
   handles no RF, and can be stopped safely.
4. Add receive event handling and descriptor delivery.
5. Add ACK timing and one constrained transmit path.
6. Add retransmission, filtering, timing, power save, aggregation, coexistence,
   and crypto-engine coordination incrementally.
7. Keep proprietary and open firmware selectable by different filenames so
   behavior can be compared without ambiguity.

OpenFWWF is useful prior art but targets much older Broadcom generations. Do
not assume its register, shared-memory, or timing model applies unchanged to
D11 revision 42.

## Testing strategy

### Unit and parser tests

- firmware header parsing, length and hash validation;
- seven-byte and eight-byte D11 record conversion;
- endian conversion and register-field helpers;
- SPROM field decoding using sanitized fixtures;
- TX/RX descriptor pack and unpack;
- channel and bandwidth validation;
- power-limit combination; and
- trace decoder alignment and polling-loop compression.

Use KUnit for kernel-only helpers and ordinary userspace tests for extraction,
conversion, trace decoding, and register-database tooling.

### Hardware integration matrix

For each supported board, record:

| Dimension | Minimum coverage |
| --- | --- |
| Boot | cold, warm, module reload |
| Band | 2.4 GHz and 5 GHz |
| Width | 20 MHz first; 40/80 only when supported |
| Security | open and WPA2-CCMP; later WPA3 if capabilities permit |
| Traffic | RX-only, TX-only, bidirectional, small packets, large packets |
| Lifecycle | scan, associate, roam, disconnect, RF kill, suspend/resume |
| Failure | AP loss, firmware stall, TX timeout, allocation failure |
| Kernel | current development kernel plus maintained LTS kernels |

Every result must identify the exact card, firmware, kernel, compiler, driver
commit, configuration, AP, channel, and test duration.

### Regression artifacts

Keep small sanitized fixtures in Git:

- firmware-container headers without proprietary payloads;
- descriptor examples with addresses and frame data masked;
- register-trace excerpts for one state transition;
- expected trace-decoder summaries; and
- SPROM layouts with MAC addresses and serial data replaced.

Large or sensitive captures should be stored separately and referenced by
content hash.

## Risk register

| Risk | Consequence | Mitigation |
| --- | --- | --- |
| Incorrect PHY/radio write | Card damage, lockup, or unintended RF emission | RX-only gates, exact revision matching, shielding, conservative writes |
| Missing calibration interpretation | Excess power, poor sensitivity, damaged PA | No TX until SPROM and power limits are independently validated |
| DMA descriptor error | Kernel memory corruption | IOMMU, DMA API debugging, guarded rings, bounded descriptors, KASAN |
| Interrupt ordering error | Interrupt storm or deadlock | Mask-first bring-up, bounded recovery, independent counters |
| Trace timing distortion | Incorrect inferred sequence | Binary per-CPU capture, disabled-path benchmark, repeated traces |
| Firmware format mismatch | PSM crash or silent corruption | Exact hashes, strict parser, stopped-core upload, readback where possible |
| Proprietary-code provenance concern | Upstream rejection | Observation logs, independent implementation, no copied decompiler output |
| Board variation | Works on one card but transmits incorrectly on another | Exact subsystem and revision allowlists; unknown hardware rejected |
| Permanent research fork | Maintenance burden and no upstream review | Engage `linux-wireless` after early milestones; structure b43-compatible code |
| Host becomes inaccessible | Slow iteration or filesystem damage | Wired management, serial/netconsole, remote reboot, disposable test root |

## Ordered initial backlog

The first implementation cycle should produce these items in order:

1. Hardware-manifest template and read-only collection script.
2. Experiment manifest recording all relevant content hashes and versions.
3. Register database schema with source and confidence fields.
4. Optional tracepoints around OSL MMIO, PCI configuration, DMA, IRQ, and DPC.
5. Userspace binary trace decoder and stable-sequence differ.
6. Baseline `wl` captures for probe, up/down, and fixed-channel changes.
7. Strict `d11ucode42.bin` to b43 firmware-container converter.
8. Current-kernel `b43ac` read-only BCMA probe restricted to one device.
9. Safe firmware upload with PSM held stopped.
10. PSM start, heartbeat, interrupt-mask, and recovery experiment.
11. AC-PHY callback audit that replaces null operations with controlled errors.
12. One-channel RX-only implementation.

Items 1 through 7 can be developed without allowing an experimental driver to
control the radio. Items 8 onward require the target hardware and recovery
environment.

## Decision gates

Stop and reassess at the following points:

- **After hardware identification:** if the card is BCM4350 `14e4:43a3`, use
  the existing `brcmfmac` host driver as the foundation; the ARM FullMAC path
  is a different project.
- **After BCMA enumeration:** if the actual D11 core is not revision 40 or 42,
  do not use the extracted firmware based only on its filename.
- **After trace capture:** if wrapper tracing misses important MMIO because a
  path is inlined or accessed through another window, add a narrowly scoped
  observation mechanism before interpreting an incomplete trace.
- **After PSM start:** if firmware requires an embedded Arm/RPC control plane
  rather than a host-driven D11 interface, revisit the SoftMAC architecture.
- **Before transmit:** do not proceed without decoded board calibration,
  regulatory intersection, an independent receiver, and RF containment.
- **Before broad refactoring:** obtain early upstream feedback on the intended
  b43 integration shape.

## Primary sources and continuing references

### Linux implementation sources

1. [Current Linux `b43` Kconfig](https://github.com/torvalds/linux/blob/master/drivers/net/wireless/broadcom/b43/Kconfig)
   identifies BCM4352/BCM4360 as AC-PHY devices and marks the support broken.
2. [Current Linux `b43` AC-PHY source](https://github.com/torvalds/linux/blob/master/drivers/net/wireless/broadcom/b43/phy_ac.c)
   shows the incomplete operations implementation.
3. [Current Linux `b43` main driver](https://github.com/torvalds/linux/blob/master/drivers/net/wireless/broadcom/b43/main.c)
   is the authoritative firmware-loading, BCMA matching, D11, and mac80211
   integration source.
4. [mac80211 driver API](https://docs.kernel.org/driver-api/80211/mac80211.html)
   defines the required Linux SoftMAC callbacks, flags, and state contracts.
5. [PCI support library](https://docs.kernel.org/driver-api/pci/pci.html)
   defines PCI device lifetime, resource, interrupt, and power-management rules.
6. [Linux firmware request API](https://docs.kernel.org/driver-api/firmware/request_firmware.html)
   defines the supported external-firmware loading interface.
7. [Linux DMA mapping guide](https://docs.kernel.org/core-api/dma-api-howto.html)
   is the primary reference for coherent and streaming DMA correctness.
8. [Linux tracepoint documentation](https://docs.kernel.org/trace/tracepoints.html)
   defines the preferred low-overhead kernel tracing mechanism.
9. [Linux Wireless regulatory documentation](https://wireless.docs.kernel.org/en/latest/en/developers/regulatory.html)
   explains cfg80211 regulatory integration and EEPROM/board restrictions.
10. [Linux patch submission guide](https://docs.kernel.org/process/submitting-patches.html)
    defines the upstream patch and review expectations.

### Reverse-engineering and firmware sources

11. [b43-tools](https://gitlab.com/mbuesch/b43-tools) provides `b43-asm`,
    `b43-dasm`, and the established D11 firmware tooling.
12. [Linux Wireless b43 developer documentation](https://wireless.docs.kernel.org/en/latest/en/users/drivers/b43/developers.html)
    records the firmware and tooling lineage.
13. [Nexmon source](https://github.com/seemoo-lab/nexmon) provides working
    examples of Broadcom Arm firmware analysis, D11 ucode extraction, ROM
    recovery, and firmware patching.
14. [Nexmon WiNTECH 2017 paper](https://www.maki.tu-darmstadt.de/media/sfb_maki/forschung_8/awards/Nexmon_2017.pdf)
    documents the Arm/D11 split and seven-byte D11 instruction storage.
15. [Armv7-A/R Architecture Reference Manual](https://developer.arm.com/documentation/ddi0406/c)
    is the authoritative reference for the extracted Arm firmware ISA.
16. [Quarkslab Broadcom reverse-engineering report](https://blog.quarkslab.com/reverse-engineering-broadcom-wireless-chipsets.html)
    independently analyzes the same BCM4352 PCI RAM firmware family.

## Immediate next milestone

The project should next implement the evidence pipeline, not a transmitting
driver: hardware manifest, reproducible experiment manifest, OSL tracepoints,
binary trace decoding, and strict D11 firmware packaging. The first hardware
milestone is Level 0 safe probe. No association or throughput work should begin
until Level 1 and RX-only Level 2 are repeatable and recoverable.
