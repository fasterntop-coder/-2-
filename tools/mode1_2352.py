#!/usr/bin/env python3
"""Independent MODE1/2352 EDC/ECC verifier used by patch recovery gates."""
from __future__ import annotations

RAW_SECTOR_SIZE = 2352
SYNC = bytes([0] + [0xFF] * 10 + [0])


def _edc_lut() -> list[int]:
    out = []
    for i in range(256):
        v = i
        for _ in range(8):
            v = (v >> 1) ^ (0xD8018001 if v & 1 else 0)
        out.append(v & 0xFFFFFFFF)
    return out


def _ecc_luts() -> tuple[list[int], list[int]]:
    f, b = [0] * 256, [0] * 256
    for i in range(256):
        j = (i << 1) ^ (0x11D if i & 0x80 else 0)
        f[i] = j & 0xFF
        b[i ^ f[i]] = i
    return f, b


EDC_LUT = _edc_lut()
ECC_F_LUT, ECC_B_LUT = _ecc_luts()


def edc(data: bytes) -> int:
    value = 0
    for byte in data:
        value = (value >> 8) ^ EDC_LUT[(value ^ byte) & 0xFF]
    return value & 0xFFFFFFFF


def _ecc_compute(src: bytes, major_count: int, minor_count: int,
                 major_mult: int, minor_inc: int) -> bytes:
    size = major_count * minor_count
    if len(src) < size:
        raise ValueError(f"ECC source too short: {len(src)} < {size}")
    dest = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        ecc_a = ecc_b = 0
        for _ in range(minor_count):
            temp = src[index]
            index += minor_inc
            if index >= size:
                index -= size
            ecc_a ^= temp
            ecc_b ^= temp
            ecc_a = ECC_F_LUT[ecc_a]
        ecc_a = ECC_B_LUT[ECC_F_LUT[ecc_a] ^ ecc_b]
        dest[major] = ecc_a
        dest[major + major_count] = ecc_a ^ ecc_b
    return bytes(dest)


def verify_mode1_sector(sector: bytes) -> dict[str, bool]:
    if len(sector) != RAW_SECTOR_SIZE:
        return {"size": False, "sync": False, "mode": False, "edc": False,
                "reserved": False, "ecc_p": False, "ecc_q": False, "valid": False}
    size_ok = True
    sync_ok = sector[:12] == SYNC
    mode_ok = sector[15] == 1
    edc_ok = int.from_bytes(sector[0x810:0x814], "little") == edc(sector[:0x810])
    reserved_ok = sector[0x814:0x81C] == bytes(8)
    ecc_p = _ecc_compute(sector[0x0C:0x81C], 86, 24, 2, 86)
    ecc_p_ok = sector[0x81C:0x8C8] == ecc_p
    ecc_q = _ecc_compute(sector[0x0C:0x8C8], 52, 43, 86, 88)
    ecc_q_ok = sector[0x8C8:0x930] == ecc_q
    valid = all((size_ok, sync_ok, mode_ok, edc_ok, reserved_ok, ecc_p_ok, ecc_q_ok))
    return {"size": size_ok, "sync": sync_ok, "mode": mode_ok, "edc": edc_ok,
            "reserved": reserved_ok, "ecc_p": ecc_p_ok, "ecc_q": ecc_q_ok,
            "valid": valid}


def assert_mode1_sector(sector: bytes, label: str = "sector") -> None:
    result = verify_mode1_sector(sector)
    if not result["valid"]:
        failed = ",".join(k for k, v in result.items() if k != "valid" and not v)
        raise ValueError(f"{label} MODE1/2352 verification failed: {failed}")


def selftest() -> None:
    sector = bytearray(RAW_SECTOR_SIZE)
    sector[:12] = SYNC
    sector[12:15] = b"\x00\x02\x00"
    sector[15] = 1
    sector[16:0x810] = bytes((i * 37 + 11) & 0xFF for i in range(2048))
    sector[0x810:0x814] = edc(sector[:0x810]).to_bytes(4, "little")
    sector[0x814:0x81C] = bytes(8)
    sector[0x81C:0x8C8] = _ecc_compute(sector[0x0C:0x81C], 86, 24, 2, 86)
    sector[0x8C8:0x930] = _ecc_compute(sector[0x0C:0x8C8], 52, 43, 86, 88)
    assert verify_mode1_sector(bytes(sector))["valid"]
    sector[100] ^= 1
    assert not verify_mode1_sector(bytes(sector))["valid"]


if __name__ == "__main__":
    selftest()
    print("PASS_MODE1_2352_SELFTEST")
