# Session Prompts and Workflow

Recorded: 2026-07-17

## Purpose

This document records the user-visible task prompts and the high-level workflow
followed during the firmware extraction, architecture analysis, modern Linux
support evaluation, open source driver planning, and implementation-checklist
preparation session. It is intended to make the reasoning and sequence of work
reproducible without preserving every terminal command or transient tool
response.

Only user task prompts and the material repository instructions are recorded.
Hidden platform instructions and internal chain-of-thought are not reproduced.

## User prompts in chronological order

### Prompt 1: extract the embedded payloads

> Write a small tool in Python to extract the firmware and ucode from
> lib/wlc_hybrid.o_shipped and have it save to fw/

This established the first concrete deliverable: a repository-local,
reproducible extractor that leaves the shipped proprietary object unchanged.

### Prompt 2: identify the execution architectures

> Analyse the files in fw/. What kind of CPU/DSP are they for?

This changed the task from simple ELF extraction to binary architecture and
processor-role identification.

### Prompt 3: preserve the analysis and sources

> Write details to docs/ including any primary sources mentioned that could be
> useful in the future.

This established a provenance requirement: conclusions, reproduction methods,
uncertainties, hashes, and source links should be retained in the repository.

### Repository instruction prompt

The user then supplied the repository's `AGENTS.md` guidance. The material
constraints applied during the remainder of the session were:

- prefix shell commands through the repository's RTK workflow;
- use CodeGraph before grep or manual source browsing when locating or
  understanding indexed code;
- treat `lib/wlc_hybrid.o_shipped` as a fixed proprietary input that must not be
  modified or regenerated;
- keep changes narrow and preserve the legacy source style;
- recognize that the repository is archived and that its final product is the
  `wl.ko` kernel module; and
- avoid host network/module changes unless carrying out deliberate hardware
  testing.

The instruction text also established that the repository's known physical
target was a BCM4360-based TP-Link Archer T8E.

### Prompt 4: evaluate practical modern-kernel options

> Given all this information provide options for getting the target hardware
> working on modern Linux kernels.

This prompted a comparison of upstream drivers, distribution-maintained
Broadcom STA packages, the archived local driver, LTS kernels, and hardware
replacement.

### Prompt 5: change the primary objective

> The main interest is reverse engineering and building a new OSS driver if
> possible.

This was the key scope correction. The objective changed from obtaining an
immediately usable network interface to understanding the hardware and building
an open source host driver.

### Prompt 6: produce the driver-development plan

> Write up a thorough plan for building a new open source driver

This requested a persistent design and execution plan rather than another
short recommendation.

### Prompt 7: record the session itself

> Write out the prompts and high level workflow that occurred in this session
> to docs/ for reference

This document is the result of that prompt.

### Prompt 8: turn the plan into an implementation checklist

> Generate a todo list from the plan and write to docs/. Ensure to include a
> comment that when performing the implemention the agent should commit to git
> after every material change.

This converted the narrative driver plan into an ordered checklist with
explicit capability milestones, safety gates, phase exit criteria, recurring
tests, and an immediate backlog. It also established a working rule for future
implementation agents: commit to Git after every material change rather than
accumulating several completed steps in one uncommitted change.

### Prompt 9: update the session record

> update docs/session_prompts_and_workflow.md

This requested that the checklist-generation work and its Git checkpoint rule
be added to the chronological session record.

## High-level workflow

### 1. Repository orientation and constraints

The repository was treated as a hybrid driver package with three relevant
layers:

```text
open Linux wrapper sources
          |
lib/wlc_hybrid.o_shipped
          |
embedded Arm firmware and D11 PSM microcode
```

The fixed object is an x86-64 relocatable ELF component, not a complete kernel
module. It is linked with the open sources in `src/shared/` and `src/wl/sys/`
to produce `wl.ko`.

Existing static analysis in [`wlc_hybrid_info.txt`](wlc_hybrid_info.txt) was
used as supporting context. In particular, it records that all unresolved
imports from the proprietary object cross the open OSL or Linux wrapper
boundary.

### 2. Firmware and microcode extractor

[`extract_firmware.py`](../extract_firmware.py) was created as a small,
dependency-free ELF parser. Its workflow is:

1. read `lib/wlc_hybrid.o_shipped` without modifying it;
2. validate that the input is a 64-bit little-endian relocatable ELF file;
3. parse the section table and the single ELF symbol table;
4. inspect object symbols rather than scanning for byte signatures;
5. select the known PCI RAM firmware symbols `dlarray_4350pci` and
   `dlarray_4352pci`;
6. select `d11ucode*` and `d11aeswakeucode*` payload symbols while excluding
   size and BOM metadata symbols;
7. validate section type, bounds, duplicate names, and expected payload
   presence; and
8. write each symbol's exact bytes to `fw/<symbol>.bin`.

The extractor deliberately avoids `pyelftools` or external binary utilities so
the extraction procedure remains self-contained. It fails closed on an
unexpected ELF layout rather than guessing.

The extraction produced:

- 2 PCI RAM firmware images;
- 71 D11 ucode images, including tiny placeholder symbols; and
- 73 output files in total.

### 3. Arm firmware architecture identification

The two `dlarray_*pci.bin` files were analyzed as flat RAM images rather than
ELF executables. The workflow combined:

- byte and word inspection;
- printable build and runtime strings;
- exception-vector decoding;
- temporary wrapping as an Arm ELF object for LLVM disassembly; and
- comparison with primary Arm architecture documentation and Broadcom/Cypress
  architecture references.

Important evidence included Thumb-2 vector branches, privileged processor-mode
instructions, CPSR/SPSR handling, and `SRSDB`. Those instructions require the
Arm A/R-profile exception model and rule out Cortex-M3's M-profile model.

The conclusion was:

- the ISA is 32-bit little-endian Armv7-R Thumb-2;
- Cortex-R4 is the high-confidence embedded core identification; and
- the images contain the HNDRTE embedded WLAN runtime, not conventional DSP
  kernels.

The BCM4350 image also contained evidence of a linked RAM window around
`0x180000` and a bootstrap that installs low exception vectors.

### 4. D11 microcode identification

The `d11ucode*` and `d11aeswakeucode*` files did not decode as Arm. They were
identified as native programs for Broadcom's proprietary D11 Programmable
State Machine.

The analysis distinguished:

- normal eight-byte instruction records represented by two little-endian
  32-bit words;
- packed seven-byte records used by some older PHY/configuration variants;
- ordinary, WoWLAN, and AES-wake PSM programs; and
- five tiny zero-filled placeholder payloads.

The D11 PSM was described as a real-time MAC-control engine that coordinates
frame timing, acknowledgements, retransmission, template/shared memory, crypto
engines, and RX/TX hardware. It is not the OFDM/DSSS signal-processing datapath
and therefore is not properly described as a general DSP.

The complete evidence, hashes, reproduction steps, and primary sources were
written to [`firmware_architecture.md`](firmware_architecture.md).

### 5. Modern Linux driver-path evaluation

The next workflow separated devices by exact PCI identity rather than Broadcom
marketing family:

| PCI identity | Driver conclusion |
| --- | --- |
| BCM4350 `14e4:43a3` | Current upstream `brcmfmac` is the appropriate open host driver and Linux Firmware supplies its RAM firmware. |
| BCM4360 `14e4:43a0` | The practical existing driver is the proprietary `wl` module maintained through distribution DKMS/akmod packaging. |
| BCM4352 `14e4:43b1` | The practical existing driver is also the proprietary `wl` module. |

Current upstream `b43` source was checked directly. It contains an AC-PHY
skeleton and recognizes BCM4352/BCM4360 as AC-PHY devices, but its Kconfig entry
remains dependent on `BROKEN` and warns that the path crashes. Its AC-PHY
operations table is incomplete.

The repository itself was also checked:

- its README declares the driver unmaintained;
- its CI matrix ends at Linux 6.7; and
- current distribution packages carry newer compatibility patches around the
  same old proprietary core.

The first practical recommendation was therefore a maintained DKMS package for
the Archer T8E. That recommendation was later subordinated to the user's
reverse-engineering objective.

### 6. Reframing around an OSS driver

Once the user clarified the goal, three different outcomes were separated:

1. **Open host driver with proprietary D11 firmware:** difficult but credible.
2. **Open host driver plus open D11 PSM firmware:** a substantially larger
   follow-on project.
3. **Replacement open BCM4350 FullMAC/Cortex-R4 firmware:** a different and much
   larger project.

For BCM4352/BCM4360, extending the existing `b43` SoftMAC architecture was
selected as the intended upstream solution because Linux already supplies:

- BCMA enumeration;
- `mac80211` and cfg80211 integration;
- D11 object/shared-memory access;
- firmware loading;
- DMA/PIO, TX/RX, interrupts, and debug infrastructure; and
- dormant support for D11 core revisions and firmware names 40 and 42.

A small out-of-tree `b43ac` research module was proposed only as a safe
bring-up vehicle. It should initially probe one exact revision with RF disabled
and later transfer proven code into `b43`.

### 7. Using the proprietary driver as a trace oracle

CodeGraph and direct source inspection established the useful instrumentation
boundary:

- `osl_readl()` and related functions wrap MMIO reads;
- `osl_writel()` and related functions wrap MMIO writes;
- PCI configuration accesses cross OSL wrappers;
- DMA mapping and allocation cross OSL wrappers; and
- interrupt ownership and deferred work cross visible functions in
  `wl_linux.c`.

The proposed reverse-engineering method was to add optional tracepoints or a
bounded per-CPU binary ring buffer to the open wrapper sources. Records would
normalize addresses to BAR/backplane offsets and include the proprietary-object
call-site offset. Scenario markers would align repeated traces for:

- probe/remove;
- interface up/down;
- channel selection;
- passive scan;
- association;
- isolated TX and RX; and
- reset and suspend/resume.

Unbounded logging from every register access was rejected because it would
distort hardware timing and overwhelm the kernel log.

### 8. Driver-development plan

The complete development plan was written to
[`oss_driver_plan.md`](oss_driver_plan.md). Its major design decisions are:

- target one exact BCM4360 board first;
- keep unknown revisions rejected by default;
- build a read-only probe before resetting the D11 core;
- convert user-extracted `d11ucode42.bin` to the external b43 firmware
  container rather than embedding it in GPL source;
- prove PSM execution with RF disabled;
- achieve fixed-channel receive before any transmission;
- require decoded board calibration and regulatory enforcement before enabling
  TX;
- add station, security, HT, and VHT support incrementally;
- contact upstream maintainers before accumulating a permanent fork; and
- postpone independently implemented open D11 firmware until the host driver is
  stable with known proprietary firmware.

The plan defines thirteen implementation phases, capability levels, explicit
exit criteria, a test matrix, provenance policy, decision gates, and a risk
register.

### 9. Actionable implementation checklist

The narrative plan was converted into
[`oss_driver_todo.md`](oss_driver_todo.md). The checklist retains:

- project-wide provenance, firmware-handling, revision-allowlist, and RF-safety
  rules;
- capability Levels 0 through 7;
- Phases 0 through 13 with task lists and hard exit gates;
- the receive-only and calibrated-transmit separation;
- recurring unit, parser, hardware, and regression-artifact checks;
- the first twelve implementation items in dependency order; and
- final completion and upstream-readiness checks.

An HTML comment and a visible instruction near the top tell an implementation
agent to commit to Git after every material change. Each commit should contain
one coherent change and its relevant test or validation, without mixing
unrelated work or accumulating multiple completed implementation steps.

## Files produced or used

| Path | Session role |
| --- | --- |
| [`extract_firmware.py`](../extract_firmware.py) | New ELF-symbol-based firmware and D11 ucode extractor |
| `fw/*.bin` | Generated firmware and D11 analysis artifacts; not intended for redistribution |
| [`firmware_architecture.md`](firmware_architecture.md) | New architecture analysis, hashes, reproduction instructions, and sources |
| [`oss_driver_plan.md`](oss_driver_plan.md) | New detailed OSS driver research and implementation plan |
| [`oss_driver_todo.md`](oss_driver_todo.md) | Ordered implementation checklist, safety gates, tests, and Git checkpoint rule |
| [`session_prompts_and_workflow.md`](session_prompts_and_workflow.md) | This chronological session record |
| [`wlc_hybrid_info.txt`](wlc_hybrid_info.txt) | Existing supporting static analysis of the proprietary object and wrapper boundary |

## Key conclusions retained from the session

1. The extracted files target two different processors: an Armv7-R embedded
   controller and the proprietary D11 PSM.
2. The D11 PSM is a real-time MAC engine, not a conventional DSP.
3. BCM4350's existing upstream route is `brcmfmac`; BCM4352/BCM4360 require a
   different SoftMAC-oriented effort.
4. Current `b43` is the strongest upstream foundation for a BCM4352/BCM4360 OSS
   host driver, but its AC-PHY implementation is presently incomplete and
   unsafe.
5. The open OSL wrapper boundary makes high-fidelity black-box tracing of the
   working proprietary driver feasible without modifying the shipped object.
6. An OSS host driver using user-extracted proprietary ucode is a realistic
   intermediate target; fully open D11 firmware is a separate milestone.
7. RX-only bring-up, calibration, power control, and regulatory enforcement are
   mandatory safety gates before active transmission.
8. Future implementation work should use focused Git commits after every
   material change so each tested step remains reviewable and recoverable.

## Recommended continuation workflow

Future agents should execute and update
[`oss_driver_todo.md`](oss_driver_todo.md), committing after every material
change. The next work should proceed in this order:

1. install and identify the exact target adapter on a recoverable test host;
2. create the immutable hardware and experiment manifests described in the
   driver plan;
3. implement optional OSL MMIO, PCI, DMA, IRQ, and lifecycle tracing;
4. capture known-good `wl` traces for probe, up/down, and fixed-channel changes;
5. implement and test the strict D11-to-b43 firmware container converter;
6. build the RF-disabled read-only `b43ac` probe against a current kernel;
7. upload and start the D11 PSM while RF remains disabled; and
8. proceed to one-channel receive-only operation only after repeatable recovery
   and validation.

The current host did not expose a Broadcom PCI device during this session, so
live trace capture and hardware bring-up remain pending.
