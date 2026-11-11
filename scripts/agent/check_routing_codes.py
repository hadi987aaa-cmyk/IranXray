#!/usr/bin/env python3
"""Fail when a routing preset references a geosite/geoip code the APK does not carry.

Xray drops a rule whose code is missing and says so only in its own log, so a typo or a
database swap silently turns a "direct"/"proxy" rule into a no-op. This reads the codes
straight out of the packaged `assets/geosite.dat` and `assets/geoip.dat` and compares them
with every `geosite:`/`geoip:` literal found in the packaged `assets/custom_routing_*`.

Usage: check_routing_codes.py <apk> [more.apk ...]
"""

import json
import sys
import zipfile

SITE_ASSET = "assets/geosite.dat"
GEO_ASSET = "assets/geoip.dat"
ROUTING_PREFIX = "assets/custom_routing_"


def varint(buf, i):
    shift = 0
    value = 0
    while True:
        byte = buf[i]
        i += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, i
        shift += 7


def fields(buf):
    i, size = 0, len(buf)
    while i < size:
        key, i = varint(buf, i)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, i = varint(buf, i)
        elif wire == 2:
            length, i = varint(buf, i)
            value = buf[i:i + length]
            i += length
        elif wire == 5:
            value = buf[i:i + 4]
            i += 4
        elif wire == 1:
            value = buf[i:i + 8]
            i += 8
        else:
            raise ValueError("unknown wire type %d" % wire)
        yield number, wire, value


def entry_codes(blob):
    """Codes of a GeoSiteList/GeoIPList: field 1 repeats an entry whose field 1 is the code."""
    codes = set()
    for number, wire, entry in fields(blob):
        if number != 1 or wire != 2:
            continue
        for entry_number, entry_wire, code in fields(entry):
            if entry_number == 1 and entry_wire == 2:
                codes.add(code.decode("utf-8", "replace").upper())
            break
    return codes


def referenced_codes(names, read):
    used = {}
    for name in names:
        if not name.startswith(ROUTING_PREFIX):
            continue
        document = json.loads(read(name).decode("utf-8"))
        for rule in document:
            for key in ("domain", "ip"):
                for value in rule.get(key, []):
                    if isinstance(value, str) and value.startswith(("geosite:", "geoip:")):
                        used.setdefault(value, set()).add(name[len(ROUTING_PREFIX):])
    return used


def check(apk):
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        for required in (SITE_ASSET, GEO_ASSET):
            if required not in names:
                print("::error file=%s::%s is missing from the APK" % (apk, required))
                return False
        site = entry_codes(archive.read(SITE_ASSET))
        geo = entry_codes(archive.read(GEO_ASSET))
        used = referenced_codes(names, archive.read)

    print("%s: geosite codes %d, geoip codes %d, referenced codes %d"
          % (apk, len(site), len(geo), len(used)))
    missing = []
    for code in sorted(used):
        kind, _, name = code.partition(":")
        table = site if kind == "geosite" else geo
        exists = name.upper() in table
        print("  %-4s %-24s %s" % ("ok" if exists else "MISS", code, ", ".join(sorted(used[code]))))
        if not exists:
            missing.append(code)

    if missing:
        print("::error::%d routing code(s) are not in the packaged databases: %s"
              % (len(missing), ", ".join(missing)))
        return False
    return True


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    ok = True
    for apk in argv[1:]:
        ok = check(apk) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
