# Embedded Firmware and D11 Microcode Architecture

This note describes the files produced in `fw/` by
[`extract_firmware.py`](../extract_firmware.py). It records the local binary
evidence, the resulting architecture identification, and sources useful for
future disassembly work. The analysis was performed on 2026-07-17.

## Conclusions

The extracted files target two distinct processors:

| Files | Execution target | Confidence |
| --- | --- | --- |
| `dlarray_4350pci.bin`, `dlarray_4352pci.bin` | 32-bit little-endian Armv7-R Thumb-2 firmware; the embedded MCU is almost certainly an Arm Cortex-R4 | Instruction set: certain; exact core model: high confidence |
| `d11ucode*`, `d11aeswakeucode*` | Broadcom's proprietary D11 Programmable State Machine (PSM) | Certain |

None of these files is program code for a conventional general-purpose DSP.
The chip has separate OFDM/DSSS baseband and radio hardware. The D11 PSM is a
specialized real-time MAC control engine which schedules and controls that
hardware; it is not the signal-processing datapath itself.

## Extracted-file inventory

The extractor produced 73 files totaling 3,173,709 bytes:

| Class | Count | Bytes |
| --- | ---: | ---: |
| PCI RAM firmware | 2 | 887,950 |
| D11 ucode, eight-byte records | 54 | 1,914,720 |
| D11 ucode, packed seven-byte records | 12 | 371,028 |
| Zero-filled ucode placeholders | 5 | 11 |

The D11 total is 71 symbols and 2,285,759 bytes. The images are alternatives
for different D11 core revisions, PHY families, and operating modes; they are
not 71 pieces of one program.

### PCI firmware identity

| File | Size | SHA-256 |
| --- | ---: | --- |
| `dlarray_4350pci.bin` | 445,717 | `a2ea8f9e9c980e5c6173b312a69baa00c34c8a06a4167ebc4039b2510c386683` |
| `dlarray_4352pci.bin` | 442,233 | `524da786fbd91f4c605d650e9f107ff29bf569356a97482ae7227e363f6c8a00` |

The printable build banners are:

```text
4350pci-bmac/debug-ag-nodis-aoe-ndoe Version: 6.30.223.0 CRC: ffcf9e98 Date: Sun 2013-12-15 19:54:33 PST FWID 01-518e42f8
4352pci-bmac/debug-ag-nodis-aoe-ndoe Version: 6.30.223.0 CRC: ff98ca92 Date: Sun 2013-12-15 19:30:36 PST FWID 01-9413fb21
```

These are flat RAM images rather than ELF files or TRX containers. `file(1)`
therefore reports only `data`; architecture identification has to come from
the instruction stream and runtime strings.

## Arm firmware analysis

### Instruction-set evidence

The start of `dlarray_4352pci.bin` is a Thumb-2 exception vector table. It
decodes as branches to local handlers:

```asm
00000000:  f000 b80e    b.w     0x20
00000004:  f000 b82e    b.w     0x64
00000008:  f000 b839    b.w     0x7e
0000000c:  f000 b844    b.w     0x98
```

The startup and exception handlers in both firmware images contain
instructions such as:

```asm
mrs     r0, apsr
msr     CPSR_fc, r0
srsdb   sp!, #0x1f
cps     #0x1f
```

`SRSDB`, explicit processor modes, and writes to the CPSR are A/R-profile
exception machinery. They are incompatible with the Armv7-M exception model
used by Cortex-M3. This establishes a 32-bit Arm A/R-profile Thumb-2 target.

The Broadcom WLAN generations covered by the available reverse-engineering
literature use Cortex-M3 (Armv7-M) or Cortex-R4 (Armv7-R) embedded MCUs. Since
the local instructions rule out the M-profile, Cortex-R4 is the high-confidence
core identification. Arm's own architecture tables identify Cortex-R4 as an
Armv7-R implementation.

The core name is still an inference rather than an identity string recovered
from these files. The defensible machine setting for disassembly is
`thumbv7r-none-eabi`; future hardware or ROM evidence could make the exact
core revision definitive.

### BCM4350 load-address evidence

The first BCM4350 vector instructions encode branches to addresses around
`0x180880`. Its bootstrap at file offset `0x80` loads a source address of
`0x180820`, copies eight words to address zero, and branches through a pointer
near `0x180add`. This is consistent with an image linked in the `0x180000` RAM
window which installs a low exception-vector page before entering the main
runtime.

The BCM4352 image instead begins with locally addressed vector branches. This
layout difference does not change the ISA identification; the exception
handler bodies use the same A/R-profile mechanisms.

### Runtime evidence

Both images contain the Broadcom HNDRTE embedded runtime and Arm-specific
support strings:

```text
hndrte.c
hndrte_arm.c
hndarm.c
TRAP %x(%x): pc %x, lr %x, sp %x, cpsr %x, spsr %x
```

They also contain PCI-dongle, BMAC, RPC, offload, packet-filter, scan, wake,
and PHY/MAC component strings. These are complete embedded WLAN control
firmware images, not isolated DSP kernels.

## D11 PSM microcode analysis

### Processor role

The D11 core contains a proprietary programmable state machine which performs
time-critical IEEE 802.11 MAC work. Its responsibilities include:

- reacting to receive events and deciding whether to drop, acknowledge, or
  forward a frame;
- scheduling transmissions, acknowledgements, and retransmissions with tight
  interframe timing;
- controlling the transmit, receive, template-RAM, shared-memory, and crypto
  engines through D11 registers;
- exchanging frames and state with the slower embedded Arm firmware.

The embedded Arm processor handles higher-level WLAN control. It loads ucode
into the D11 core's ucode memory during initialization. On FullMAC designs the
chip-specific ucode may also be carried inside the monolithic Arm RAM firmware.

The `d11ucode*` files in this directory are native D11 PSM machine code, not
Arm instructions. A specialized tool such as `b43-dasm` is required to decode
them.

### Eight-byte form

Fifty-four nonempty images contain eight bytes per PSM instruction. For
example, the start of `d11ucode40.bin` is:

```text
raw bytes:  4e 10 00 03 60 bc 01 00  3d 0e f0 02 de bf 03 00
LE words:   0300104e 0001bc60          02f00e3d 0003bfde
```

Each instruction is represented by two 32-bit words. Only seven of the eight
bytes carry information in this generation, so the high byte visible in the
unpacked form is normally zero.

### Packed seven-byte form

Twelve images omit the unused eighth byte and store exactly seven bytes per
PSM instruction:

```text
d11ucode16_sslpn.bin
d11ucode16_sslpn_nobt.bin
d11ucode19_sslpn.bin
d11ucode19_sslpn_nobt.bin
d11ucode20_sslpn.bin
d11ucode20_sslpn_nobt.bin
d11ucode21_sslpn.bin
d11ucode21_sslpn_nobt.bin
d11ucode22_sslpn.bin
d11ucode25_lcn.bin
d11ucode27_sslpn.bin
d11ucode33_lcn40.bin
```

Every one of their file sizes is divisible by seven. Their record byte order
also differs from the raw little-endian two-word representation. Do not turn
these into eight-byte images by blindly appending a zero; use Nexmon's
`ucodeext` logic or an equivalent format-aware conversion before passing them
to tools which expect unpacked records.

### Placeholders

Five extracted symbols are tiny, entirely zero-filled placeholders rather
than usable programs:

| File | Size |
| --- | ---: |
| `d11ucode9.bin` | 4 |
| `d11ucode35_lcn40.bin` | 1 |
| `d11ucode36_mimo.bin` | 4 |
| `d11ucode37_lcn40.bin` | 1 |
| `d11ucode38_lcn40.bin` | 1 |

The original Broadcom object retains these symbols so the compiled selection
logic can refer to a uniform set of names even when a particular payload was
not built into this release.

### Naming and modes

The number in names such as `d11ucode40` identifies the intended D11 core
revision under Broadcom's firmware naming convention. Suffixes distinguish
PHY or configuration families, including `mimo`, `lp`, `sslpn`, `lcn`, and
`lcn40`.

`d11ucode_wowl*` images implement Wake on Wireless LAN behavior on the same
D11 PSM. `d11aeswakeucode*` images are also PSM code; the name does not imply
an AES DSP. Broadcom's published architecture describes the PSM as selecting
and coordinating dedicated WEP/TKIP/AES crypto accelerators.

## Reproducing the local analysis

Basic inspection:

```sh
file fw/dlarray_4350pci.bin fw/dlarray_4352pci.bin
xxd -g 4 -l 256 fw/dlarray_4350pci.bin
xxd -g 4 -l 256 fw/dlarray_4352pci.bin
strings -a -t x -n 5 fw/dlarray_4350pci.bin
strings -a -t x -n 5 fw/dlarray_4352pci.bin
xxd -g 4 -l 128 fw/d11ucode40.bin
```

LLVM can disassemble the flat Arm images after wrapping them in a temporary
ELF object. The wrapper does not modify the original firmware:

```sh
llvm-objcopy \
  -I binary \
  -O elf32-littlearm \
  -B arm \
  --rename-section=.data=.text,alloc,load,readonly,code \
  fw/dlarray_4352pci.bin /tmp/dlarray_4352pci.elf

llvm-objdump \
  -D \
  --section=.text \
  --triple=thumbv7r-none-eabi \
  --start-address=0 \
  --stop-address=0x200 \
  /tmp/dlarray_4352pci.elf
```

Repeat with `dlarray_4350pci.bin`. The flat binary does not provide symbols or
code/data boundaries, so whole-image linear disassembly will also decode
literal pools, tables, and strings as false instructions. Use vector targets,
literal references, runtime strings, and control flow to establish regions.

For D11 work, build `b43-dasm` and related tools from `b43-tools`. Convert the
seven-byte form before disassembly, as described above.

## Sources for future work

### Authoritative architecture references

1. [Arm Toolchain for Embedded: supported architectures and cores](https://developer.arm.com/Tools%20and%20Software/Arm%20Toolchain%20for%20Embedded)
   maps Armv7-R to Cortex-R4/R5/R7/R8 and Armv7-M to Cortex-M3. This supports
   the profile-to-core-family part of the Arm identification.
2. [Arm Cortex-R Processor Comparison Table](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/Cortex-A%20R%20M%20datasheets/Arm%20Cortex-R%20Comparison%20Table.pdf?hash=FD7C3BA51CC77120C6E8AE9F4F522E762BF32334&la=en&revision=74d60ed8-f68b-48c4-a888-9a8b128a2cbe)
   is Arm's processor-family summary and identifies Cortex-R4 as Armv7-R.
3. [Arm Architecture Reference Manual, Armv7-A and Armv7-R edition](https://developer.arm.com/documentation/ddi0406/c)
   is the definitive instruction and exception-model reference for validating
   the T32, `SRS`, processor-mode, and CPSR evidence in these images.
4. [Infineon/Cypress CYW43438 datasheet, document 002-14796](https://www.infineon.com/assets/row/public/documents/30/49/infineon-cyw43438-datasheet-en.pdf)
   documents the related Broadcom/Cypress WLAN architecture: HNDRTE on an
   embedded Arm processor, D11 ucode for time-critical tasks, PSM instruction
   and shared memories, and dedicated cipher engines. See especially the MAC
   description around pages 25-26 and device software architecture around
   pages 47-48. It is not a BCM4350 or BCM4352 datasheet and must be used only
   as architectural corroboration.

### Primary reverse-engineering research

5. [Nexmon: Build Your Own Wi-Fi Testbeds With Low-Level MAC and PHY Access Using Firmware Patches on Off-the-Shelf Mobile Devices](https://www.maki.tu-darmstadt.de/media/sfb_maki/forschung_8/awards/Nexmon_2017.pdf),
   WiNTECH 2017. This paper provides the most useful public block diagram of
   the Arm/D11 split, describes the PSM's real-time role, documents loading
   ucode through D11 object memory, and explicitly explains that some firmware
   stores seven of each eight ucode bytes. See pages 1 and 5.
6. [Nexmon source repository](https://github.com/seemoo-lab/nexmon) contains
   the firmware-patching framework and the `ucodeext` workflow referenced by
   the paper.

### Exact-image and tooling references

7. [Quarkslab: Reverse-engineering Broadcom wireless chipsets](https://blog.quarkslab.com/reverse-engineering-broadcom-wireless-chipsets.html)
   independently extracts `dlarray_4352pci` from Broadcom's `wl` object and
   reports the exact 442,233-byte size and firmware banner found here. It also
   discusses the Arm Cortex-M3/Cortex-R4 split and flat RAM firmware images.
8. [b43-tools upstream repository](https://gitlab.com/mbuesch/b43-tools)
   provides `b43-asm`, `b43-dasm`, firmware conversion tools, and supporting
   documentation for the proprietary D11 instruction set.
9. [Linux Wireless b43 developer documentation](https://wireless.docs.kernel.org/en/latest/en/users/drivers/b43/developers.html)
   points to `b43-tools` as the maintained firmware assembler/disassembler
   toolset and records the firmware-extraction lineage.

The broader provenance and static analysis of `lib/wlc_hybrid.o_shipped` is in
[`wlc_hybrid_info.txt`](wlc_hybrid_info.txt).
