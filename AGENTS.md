# Repository Guidelines

## Project Structure & Module Organization

This repository packages Broadcom's 64-bit `wl` Linux kernel module and is archived. Driver sources live under `src/`: `src/wl/sys/` contains the Linux, Wireless Extensions, and cfg80211 integration; `src/shared/` contains the OS abstraction layer; and `src/include/` plus `src/common/include/` provide shared headers and protocol definitions. `lib/wlc_hybrid.o_shipped` is the prebuilt proprietary driver object linked into `wl.ko`; do not modify or regenerate it. The root `Makefile` drives Kbuild, `dkms.conf` provides DKMS metadata, and `.github/workflows/ci.yaml` defines compatibility builds.

## Build, Test, and Development Commands

- `make`: build `wl.ko` against the running kernel's headers.
- `make clean`: remove Kbuild outputs for the configured kernel tree.
- `make KBASE=/lib/modules/<kernel-version>`: build against a specific installed kernel.
- `make API=CFG80211` or `make API=WEXT`: force an API when diagnosing compatibility.
- `git diff --check`: catch whitespace errors before submitting a patch.

Kernel headers and a matching compiler must be installed. `make install`, `depmod -A`, and `modprobe wl` change the host system and networking; use them only for deliberate hardware testing with conflicting modules (`ssb`, `bcma`, `b43`, and `brcmsmac`) unloaded.

## Coding Style & Naming Conventions

Keep patches narrow and follow the style of the surrounding legacy C code. Preserve tab-based indentation, existing brace placement, and preprocessor layout rather than reformatting unrelated lines. Use established prefixes: `wl_*` for driver functions, `bcm*` for shared Broadcom helpers, and uppercase names for macros. Makefile recipes require literal tabs. There is no repository-wide formatter or linter.

## Testing Guidelines

There is no unit-test suite or coverage requirement. A successful module build is the primary check. Run `make clean && make` on the target kernel and, for compatibility changes, repeat against every affected kernel series. Confirm both cfg80211 and WEXT paths when changing conditional API code. Report kernel versions and compiler versions in the pull request.

## Commit & Pull Request Guidelines

Use a short, imperative commit subject. History commonly uses scoped prefixes such as `ci: Test build on Linux 6.7` and `doc: Update links`; driver fixes use direct summaries such as `Use pde_data() instead of PDE_DATA()`. Pull requests should explain the kernel/API incompatibility, identify affected versions, link relevant issues or upstream patches, and list exact build commands and results. Avoid bundling formatting cleanup with functional compatibility fixes.
