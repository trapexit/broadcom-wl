#!/usr/bin/env python3
"""Extract embedded firmware and D11 ucode from wlc_hybrid.o_shipped."""

import argparse
import struct
import sys
from pathlib import Path


ELF_HEADER = struct.Struct("<16sHHIQQQIHHHHHH")
SECTION_HEADER = struct.Struct("<IIQQQQIIQQ")
SYMBOL = struct.Struct("<IBBHQQ")

ET_REL = 1
SHT_PROGBITS = 1
SHT_SYMTAB = 2
STT_OBJECT = 1

FIRMWARE_NAMES = {"dlarray_4350pci", "dlarray_4352pci"}
UCODE_PREFIXES = ("d11ucode", "d11aeswakeucode")
UCODE_METADATA_SUFFIXES = ("sz", "_bommajor", "_bomminor")


def fail(message):
    raise ValueError(message)


def parse_sections(image):
    if len(image) < ELF_HEADER.size:
        fail("input is too small to be an ELF file")

    header = ELF_HEADER.unpack_from(image)
    ident = header[0]
    if ident[:4] != b"\x7fELF":
        fail("input is not an ELF file")
    if ident[4] != 2 or ident[5] != 1:
        fail("only 64-bit little-endian ELF files are supported")
    if header[1] != ET_REL:
        fail("input is not an ELF relocatable object")

    section_offset = header[6]
    section_entry_size = header[11]
    section_count = header[12]
    if section_entry_size != SECTION_HEADER.size:
        fail("unexpected ELF section-header size")
    if section_offset + section_count * section_entry_size > len(image):
        fail("ELF section table extends beyond the input")

    return [
        SECTION_HEADER.unpack_from(image, section_offset + i * section_entry_size)
        for i in range(section_count)
    ]


def string_at(table, offset):
    if offset >= len(table):
        fail("symbol name offset extends beyond its string table")
    end = table.find(b"\0", offset)
    if end < 0:
        fail("unterminated symbol name")
    return table[offset:end].decode("ascii")


def read_symbols(image, sections):
    symtabs = [section for section in sections if section[1] == SHT_SYMTAB]
    if len(symtabs) != 1:
        fail("expected exactly one ELF symbol table")

    symtab = symtabs[0]
    symtab_offset, symtab_size = symtab[4], symtab[5]
    string_table_index, symbol_size = symtab[6], symtab[9]
    if symbol_size != SYMBOL.size or symtab_size % symbol_size:
        fail("unexpected ELF symbol-table layout")
    if string_table_index >= len(sections):
        fail("invalid ELF symbol string-table index")

    string_section = sections[string_table_index]
    strings = image[string_section[4]:string_section[4] + string_section[5]]
    if len(strings) != string_section[5]:
        fail("ELF symbol string table extends beyond the input")
    if symtab_offset + symtab_size > len(image):
        fail("ELF symbol table extends beyond the input")

    for offset in range(symtab_offset, symtab_offset + symtab_size, symbol_size):
        name_offset, info, _, section_index, value, size = SYMBOL.unpack_from(
            image, offset
        )
        if info & 0x0f != STT_OBJECT:
            continue
        yield string_at(strings, name_offset), section_index, value, size


def payload_kind(name):
    if name in FIRMWARE_NAMES:
        return "firmware"
    if name.startswith(UCODE_PREFIXES) and not name.endswith(
        UCODE_METADATA_SUFFIXES
    ):
        return "ucode"
    return None


def extract_payloads(image, sections):
    payloads = []
    names = set()

    for name, section_index, value, size in read_symbols(image, sections):
        kind = payload_kind(name)
        if kind is None:
            continue
        if name in names:
            fail("duplicate payload symbol: " + name)
        if section_index >= len(sections):
            fail("invalid section index for payload symbol: " + name)

        section = sections[section_index]
        if section[1] != SHT_PROGBITS:
            fail("payload is not stored in a PROGBITS section: " + name)
        if value + size > section[5]:
            fail("payload extends beyond its ELF section: " + name)

        start = section[4] + value
        payload = image[start:start + size]
        if len(payload) != size:
            fail("payload extends beyond the input: " + name)

        names.add(name)
        payloads.append((kind, name, payload))

    if not FIRMWARE_NAMES.issubset(names):
        missing = ", ".join(sorted(FIRMWARE_NAMES - names))
        fail("missing expected firmware symbol(s): " + missing)
    if not any(kind == "ucode" for kind, _, _ in payloads):
        fail("no D11 ucode symbols found")

    return sorted(payloads)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("lib/wlc_hybrid.o_shipped"),
        help="ELF object to extract (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("fw"),
        help="output directory (default: %(default)s)",
    )
    args = parser.parse_args()

    try:
        image = args.input.read_bytes()
        sections = parse_sections(image)
        payloads = extract_payloads(image, sections)
        args.output.mkdir(parents=True, exist_ok=True)
        for _, name, payload in payloads:
            (args.output / (name + ".bin")).write_bytes(payload)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        parser.exit(1, "error: {}\n".format(error))

    firmware_count = sum(kind == "firmware" for kind, _, _ in payloads)
    ucode_count = sum(kind == "ucode" for kind, _, _ in payloads)
    print(
        "Extracted {} firmware and {} ucode images to {}".format(
            firmware_count, ucode_count, args.output
        )
    )


if __name__ == "__main__":
    sys.exit(main())
