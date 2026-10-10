#!/usr/bin/env python3
"""verifica_minos_macos.py — comprova el `minos` (LC_BUILD_VERSION /
LC_VERSION_MIN_MACOSX) de TOTS els Mach-O d'un arbre, **sense `otool`**.

Per què existeix: un `.app` pot fallar a High Sierra si QUALSEVOL dels binaris
que porta a dins (Python, frameworks de Qt, `*.so` de numpy/sip, l'executable,
els natius, ffmpeg…) declara un `minos` superior a 10.13. El `tag` de la roda
(p. ex. `macosx_10_9`) NO garanteix el `minos` real del binari, i els binaris
`universal2` poden tenir `minos` diferent per fatia (arm64 sol ser 11.0; només
importa la fatia **x86_64** per a High Sierra Intel).

Ús:
    verifica_minos_macos.py [--max 10.13] [--arch x86_64] RUTA [RUTA…]

Retorna 0 si cap binaris supera el màxim; 1 si n'hi ha algun (i els llista).
"""
import argparse
import os
import struct
import sys

LC_VERSION_MIN_MACOSX = 0x24
LC_BUILD_VERSION = 0x32
MH_MAGIC_64 = 0xFEEDFACF
MH_CIGAM_64 = 0xCFFAEDFE
MH_MAGIC = 0xFEEDFACE
MH_CIGAM = 0xCEFAEDFE
FAT_MAGIC = 0xCAFEBABE
FAT_CIGAM = 0xBEBAFECA

ARCHS = {"x86_64": 0x01000007, "arm64": 0x0100000C, "i386": 7, "arm": 12}


def _dec(v):
    """uint32 minos (X<<16|Y<<8|Z) -> 'X.Y.Z'."""
    return f"{v >> 16}.{(v >> 8) & 0xFF}.{v & 0xFF}"


def _vnum(s):
    try:
        a = s.split(".")
        return int(a[0]) + (int(a[1]) / 100.0 if len(a) > 1 else 0)
    except (ValueError, IndexError):
        return -1.0


def _parse_thin(data, off, want):
    magic = struct.unpack_from(">I", data, off)[0]
    if magic in (MH_MAGIC_64, MH_CIGAM_64):
        endian, is64 = (">" if magic == MH_MAGIC_64 else "<"), True
    elif magic in (MH_MAGIC, MH_CIGAM):
        endian, is64 = (">" if magic == MH_MAGIC else "<"), False
    else:
        return []
    if want is not None:
        cpu = struct.unpack_from(endian + "I", data, off + 4)[0]
        if (cpu & 0xFFFFFFFF) != want:
            return []
    hsz = 32 if is64 else 28
    ncmds = struct.unpack_from(endian + "I", data, off + 16)[0]
    p, res = off + hsz, []
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from(endian + "II", data, p)
        if cmd == LC_BUILD_VERSION:
            res.append(_dec(struct.unpack_from(endian + "I", data, p + 12)[0]))
        elif cmd == LC_VERSION_MIN_MACOSX:
            res.append(_dec(struct.unpack_from(endian + "I", data, p + 8)[0]))
        if cmdsize == 0:
            break
        p += cmdsize
    return res


def _minos(data, want):
    magic = struct.unpack_from(">I", data, 0)[0]
    if magic in (FAT_MAGIC, FAT_CIGAM):
        endian = ">" if magic == FAT_MAGIC else "<"
        nfat = struct.unpack_from(endian + "I", data, 4)[0]
        out = []
        for i in range(nfat):
            off = struct.unpack_from(endian + "I", data, 8 + i * 20 + 8)[0]
            out += _parse_thin(data, off, want)
        return out
    return _parse_thin(data, 0, want)


def _fitxers(rutes):
    for r in rutes:
        if os.path.isdir(r):
            for arrel, _, fs in os.walk(r):
                for f in fs:
                    yield os.path.join(arrel, f)
        else:
            yield r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max", default="10.13",
                    help="minos màxim admès (per defecte 10.13)")
    ap.add_argument("--arch", default="x86_64",
                    help="arquitectura a mirar (per defecte x86_64)")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("rutes", nargs="+")
    args = ap.parse_args(argv)
    want = ARCHS.get(args.arch)

    vists, pitjors, dolents = 0, [], []
    for f in _fitxers(args.rutes):
        try:
            with open(f, "rb") as fh:
                data = fh.read(4) + fh.read()
        except OSError:
            continue
        if len(data) < 4 or struct.unpack(">I", data[:4])[0] not in (
                MH_MAGIC_64, MH_CIGAM_64, MH_MAGIC, MH_CIGAM,
                FAT_MAGIC, FAT_CIGAM):
            continue
        valors = [v for v in _minos(data, want) if _vnum(v) >= 0]
        if not valors:
            continue
        vists += 1
        top = max(valors, key=_vnum)
        pitjors.append((top, f))
        if _vnum(top) > _vnum(args.max):
            dolents.append((f, top))

    if not args.quiet:
        print(f"Mach-O comprovats ({args.arch}): {vists}")
        for v, f in sorted(pitjors, key=lambda kv: _vnum(kv[0]),
                           reverse=True)[:15]:
            print(f"  {v:>10}  {f}")

    if dolents:
        print(f"\n::error:: {len(dolents)} binaris amb minos > {args.max} "
              f"({args.arch}):")
        for f, v in dolents:
            print(f"   {v}  {f}")
        return 1
    print(f"\nOK: cap binari ({args.arch}) supera {args.max}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
