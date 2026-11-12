#!/usr/bin/env python3

import os
import re
import json
import base64
import ipaddress
import uuid
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, time as datetime_time
from zoneinfo import ZoneInfo
from urllib.parse import quote
import random
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])

CONFIG_DIR = os.environ.get("XRAY_CONFIG_DIR", "/etc/v2ray-agent/xray/conf")
APP_DIR = os.environ.get("BOT_APP_DIR", "/opt/xray-telegram-bot")
BACKUP_DIR = os.path.join(APP_DIR, "backups")
DB_FILE = os.path.join(APP_DIR, "data.db")

XRAY_BIN = os.environ.get("XRAY_BIN", "xray")
XRAY_API = os.environ.get("XRAY_API", "127.0.0.1:10085")

USAGE_MONITOR_ENABLED = True
XRAY_STATE_FILE = os.path.join(APP_DIR, "xray_state.json")

SERVER_IP = os.environ.get("SERVER_IP", "").strip()
XHTTP_PORT = int(os.environ.get("XHTTP_PORT", "443"))

XHTTP_IPV6 = [x.strip() for x in os.environ.get("XHTTP_IPV6", "").split(",") if x.strip()]

def choose_xhttp_ipv6():
    return random.choice(XHTTP_IPV6)


os.makedirs(BACKUP_DIR, exist_ok=True)

# =========================================================
# INBOUNDS
# =========================================================

# Inbounds this server actually runs, written by the installer and keyed by a stable id:
#   {"vless-443-XHTTP": {"file": "08_VLESS_XHTTP_inbounds.json", "tag": "VLESS_XHTTP",
#                        "name": "VLESS + XHTTP + Reality", "protocol": "vless",
#                        "port": 443, "network": "xhttp", "security": "reality"}}
INBOUNDS_FILE = os.environ.get(
    "INBOUNDS_FILE",
    os.path.join(APP_DIR, "inbounds.json")
)


def load_inbounds():
    """Read the registry the installer wrote.

    Falls back to the single-inbound environment an older installation used, so an upgrade
    does not need a reinstall.
    """
    try:
        with open(INBOUNDS_FILE, "r", encoding="utf-8") as f:
            found = json.load(f)

        if found:
            return found
    except Exception:
        pass

    single = os.environ.get("XHTTP_DIRECT_CONFIG", "")

    if single:
        return {
            "XHTTP": {
                "file": os.path.basename(single),
                "tag": os.environ.get("XHTTP_DIRECT_TAG", ""),
                "name": "VLESS + XHTTP + Reality",
                "protocol": "vless",
                "network": "xhttp",
                "security": "reality",
                "port": int(os.environ.get("XHTTP_PORT", "443")),
            }
        }

    return {}


INBOUNDS = load_inbounds()


def inbound_of(data, kind):
    """The inbound `kind` names inside `data`, matched by tag instead of by position."""
    entry = INBOUNDS.get(kind) or {}
    tag = entry.get("tag")

    for inbound in data.get("inbounds", []):

        if tag and inbound.get("tag") == tag:
            return inbound

    raise KeyError(
        f"inbound '{kind}' (tag={tag!r}) is not in {entry.get('file')}"
    )

# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():
    conn = db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            kind TEXT NOT NULL,
            quota_bytes INTEGER,
            used_bytes INTEGER NOT NULL DEFAULT 0,
            last_xray_bytes INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            hostname TEXT,
            server_ip TEXT
        )
    """)

    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }

    # Safe migration for databases created by older bot versions.
    if "hostname" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN hostname TEXT")
    if "server_ip" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN server_ip TEXT")

    conn.commit()
    conn.close()


# =========================================================
# SECURITY
# =========================================================

def admin(update: Update):

    return (
        update.effective_chat is not None
        and update.effective_chat.id == ADMIN_CHAT_ID
    )


async def denied(update: Update):

    if update.message:
        await update.message.reply_text("⛔ دسترسی ندارید.")


# =========================================================
# FILE HELPERS
# =========================================================

def config_path(kind):

    return os.path.join(
        CONFIG_DIR,
        INBOUNDS[kind]["file"]
    )


def load_config(kind):

    with open(
        config_path(kind),
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def save_config(kind, data):

    filename = INBOUNDS[kind]["file"]

    now = datetime.now()

    backup_dir = os.path.join(
        BACKUP_DIR,
        now.strftime("%Y-%m-%d")
    )

    os.makedirs(
        backup_dir,
        exist_ok=True
    )

    backup = os.path.join(
        backup_dir,
        f"{filename}.{now.strftime('%H%M%S')}.bak"
    )

    shutil.copy2(
        config_path(kind),
        backup
    )

    tmp = config_path(kind) + ".tmp"

    with open(
        tmp,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

        f.write("\n")

    os.replace(
        tmp,
        config_path(kind)
    )


# =========================================================
# XRAY
# =========================================================

def test_xray():

    result = subprocess.run(
        [
            XRAY_BIN,
            "run",
            "-test",
            "-confdir",
            CONFIG_DIR
        ],
        capture_output=True,
        text=True,
        timeout=30
    )

    return (
        result.returncode == 0,
        result.stdout + result.stderr
    )


def test_config_data(kind, data):
    """Validate a candidate inbound without touching the live configuration.

    The previous version wrote the candidate over the live file, ran the test and restored the
    original afterwards; a crash inside that window left production with a configuration nobody
    had validated.
    """

    import tempfile

    workdir = tempfile.mkdtemp(prefix="xray-test-")

    try:

        for entry in os.listdir(CONFIG_DIR):

            source = os.path.join(CONFIG_DIR, entry)

            if os.path.isfile(source):
                shutil.copy2(
                    source,
                    os.path.join(workdir, entry)
                )

        target = os.path.join(
            workdir,
            INBOUNDS[kind]["file"]
        )

        with open(target, "w", encoding="utf-8") as f:

            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

        result = subprocess.run(
            [XRAY_BIN, "run", "-test", "-confdir", workdir],
            capture_output=True,
            text=True,
            timeout=30
        )

        return (
            result.returncode == 0,
            result.stdout + result.stderr
        )

    finally:

        shutil.rmtree(workdir, ignore_errors=True)


def restart_xray():

    try:

        result = subprocess.run(
            ["systemctl", "restart", "xray"],
            capture_output=True,
            text=True,
            timeout=30
        )

        restart_rc = result.returncode

        time.sleep(2)

        check = subprocess.run(
            [
                "systemctl",
                "is-active",
                "xray"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        status = check.stdout.strip()

        print(
            f"RESTART DEBUG: "
            f"restart_rc={restart_rc}, "
            f"active_rc={check.returncode}, "
            f"status={status!r}, "
            f"output={(result.stdout + result.stderr)!r}",
            flush=True
        )

        if check.returncode == 0 and status == "active":

            return True, "Xray is active."

        return False, (
            f"Xray status: {status}\n"
            + result.stdout
            + result.stderr
            + check.stderr
        )

    except Exception as e:

        return False, str(e)


# =========================================================
# CLIENT HELPERS
# =========================================================

def client_payload(kind, uuid_value, name):
    """The client object Xray expects for this inbound's protocol.

    Trojan authenticates with a password, everything else with a uuid. The bot stores the same
    generated value in its database either way, so its own bookkeeping stays uniform.
    """
    if (INBOUNDS.get(kind) or {}).get("protocol") == "trojan":
        return {"password": uuid_value, "email": name}

    return {"id": uuid_value, "email": name}


def find_client(kind, identifier):

    data = load_config(kind)

    clients = (
        inbound_of(data, kind)
        ["settings"]
        ["clients"]
    )

    for client in clients:

        if (
            client.get("email") == identifier
            or client.get("id") == identifier
            or client.get("password") == identifier
        ):

            return data, client

    return data, None


def all_clients():

    result = []

    for kind in INBOUNDS:

        try:

            data = load_config(kind)

            clients = (
                inbound_of(data, kind)
                ["settings"]
                ["clients"]
            )

            for client in clients:

                result.append({
                    "email": client.get("email"),
                    "uuid": client.get("id"),
                    "kind": kind,
                    "protocol": INBOUNDS[kind]["name"],
                })

        except Exception as e:

            print(
                f"all_clients error {kind}: {e}",
                flush=True
            )

    return result


# =========================================================
# DATABASE USER
# =========================================================

def db_user(uuid_value, kind=None):

    conn = db()

    if kind is None:

        row = conn.execute(
            "SELECT * FROM users WHERE uuid=? LIMIT 1",
            (uuid_value,)
        ).fetchone()

    else:

        row = conn.execute(
            "SELECT * FROM users WHERE uuid=? AND kind=? LIMIT 1",
            (uuid_value, kind)
        ).fetchone()

    conn.close()

    return row


def db_user_email(email):

    conn = db()

    row = conn.execute(
        "SELECT * FROM users WHERE email=?",
        (email,)
    ).fetchone()

    conn.close()

    return row


def create_db_user(
    uuid_value,
    email,
    kind,
    quota_bytes,
    hostname=None,
    server_ip=None
):

    now = datetime.now().isoformat()

    conn = db()

    conn.execute(
        """
        INSERT INTO users
        (
            uuid,
            email,
            kind,
            quota_bytes,
            used_bytes,
            last_xray_bytes,
            enabled,
            created_at,
            updated_at,
            hostname,
            server_ip
        )
        VALUES (?, ?, ?, ?, 0, 0, 1, ?, ?, ?, ?)
        """,
        (
            uuid_value,
            email,
            kind,
            quota_bytes,
            now,
            now,
            hostname,
            server_ip
        )
    )

    conn.commit()
    conn.close()


def remove_db_user(uuid_value, kind=None):

    conn = db()

    if kind is None:

        conn.execute(
            "DELETE FROM users WHERE uuid=?",
            (uuid_value,)
        )

    else:

        conn.execute(
            "DELETE FROM users WHERE uuid=? AND kind=?",
            (uuid_value, kind)
        )

    conn.commit()
    conn.close()


# =========================================================
# QUOTA
# =========================================================

def quota_text(quota):

    if quota is None:
        return "نامحدود"

    gb = quota / (1024 ** 3)

    if gb.is_integer():
        return f"{int(gb)} GB"

    return f"{gb:.2f} GB"


def used_text(value):

    return f"{value / (1024 ** 3):.2f} GB"


def quota_bytes_from_gb(gb):

    return int(
        gb * 1024 * 1024 * 1024
    )


# =========================================================
# XRAY STATS
# =========================================================

def get_xray_stats():

    try:

        result = subprocess.run(
            [
                XRAY_BIN,
                "api",
                "statsquery",
                f"--server={XRAY_API}"
            ],
            capture_output=True,
            text=True,
            timeout=20
        )

        if result.returncode != 0:

            print(
                "STATS ERROR:",
                result.stdout,
                result.stderr,
                flush=True
            )

            return {}

        data = json.loads(result.stdout)

        stats = {}

        for item in data.get("stat", []):

            name = item.get("name")
            value = item.get("value")

            if (
                name
                and value is not None
            ):

                try:
                    stats[name] = int(value)
                except:
                    pass

        return stats

    except Exception as e:

        print(
            "STATS EXCEPTION:",
            e,
            flush=True
        )

        return {}


def get_xray_identity():
    try:
        result = subprocess.run(
            ["pidof", "xray"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0 or not result.stdout.strip():
            return None, None

        pid = int(result.stdout.strip().split()[0])

        try:
            boot_id = Path(
                "/proc/sys/kernel/random/boot_id"
            ).read_text(
                encoding="utf-8"
            ).strip()
        except Exception:
            boot_id = None

        return pid, boot_id

    except Exception as e:
        print(
            "XRAY IDENTITY ERROR:",
            e,
            flush=True
        )
        return None, None


def load_xray_state():
    try:
        with open(
            XRAY_STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)
    except Exception:
        return {}


def save_xray_state(pid, boot_id):
    try:
        tmp = XRAY_STATE_FILE + ".tmp"

        with open(
            tmp,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                {
                    "pid": pid,
                    "boot_id": boot_id
                },
                f,
                ensure_ascii=False,
                indent=2
            )
            f.write("\n")

        os.replace(
            tmp,
            XRAY_STATE_FILE
        )

    except Exception as e:
        print(
            "XRAY STATE SAVE ERROR:",
            e,
            flush=True
        )


def collect_usage():

    stats = get_xray_stats()

    if not stats:
        return

    current_pid, current_boot_id = get_xray_identity()
    old_state = load_xray_state()

    xray_restarted = False

    if current_pid is not None:
        if (
            old_state.get("pid") is not None
            and old_state.get("pid") != current_pid
        ):
            xray_restarted = True

        if (
            old_state.get("boot_id") is not None
            and current_boot_id is not None
            and old_state.get("boot_id") != current_boot_id
        ):
            xray_restarted = True

    if current_pid is not None:
        save_xray_state(
            current_pid,
            current_boot_id
        )

    conn = db()

    users = conn.execute(
        "SELECT * FROM users WHERE enabled=1"
    ).fetchall()

    for user in users:
        email = user["email"]

        up_key = f"user>>>{email}>>>traffic>>>uplink"
        down_key = f"user>>>{email}>>>traffic>>>downlink"

        current = stats.get(up_key, 0) + stats.get(down_key, 0)
        previous = user["last_xray_bytes"]

        if xray_restarted:
            delta = current
        elif current >= previous:
            delta = current - previous
        else:
            delta = current

        new_used = user["used_bytes"] + delta

        # Record usage only. Never change enabled status because of a quota.
        conn.execute(
            """
            UPDATE users
            SET used_bytes=?,
                last_xray_bytes=?,
                updated_at=?
            WHERE uuid=? AND kind=?
            """,
            (
                new_used,
                current,
                datetime.now().isoformat(),
                user["uuid"],
                user["kind"]
            )
        )

    conn.commit()
    conn.close()

    exceeded = []

    lookup = db()

    over = lookup.execute(
        "SELECT uuid, email, kind, used_bytes, quota_bytes "
        "FROM users "
        "WHERE enabled=1 AND quota_bytes IS NOT NULL AND used_bytes >= quota_bytes"
    ).fetchall()

    lookup.close()

    for row in over:

        if not disable_user_in_xray(row["kind"], row["uuid"]):
            continue

        mark = db()

        mark.execute(
            "UPDATE users SET enabled=0, updated_at=? WHERE uuid=? AND kind=?",
            (
                datetime.now().isoformat(),
                row["uuid"],
                row["kind"]
            )
        )

        mark.commit()
        mark.close()

        exceeded.append(
            (
                row["email"],
                row["used_bytes"],
                row["quota_bytes"]
            )
        )

    if xray_restarted:
        print(
            "XRAY COUNTER RESET DETECTED: "
            f"pid={current_pid} "
            f"boot_id={current_boot_id}",
            flush=True
        )

    return exceeded

# =========================================================
# DISABLE USER
# =========================================================

def disable_user_in_xray(kind, uuid_value):

    try:

        data = load_config(kind)

        clients = (
            inbound_of(data, kind)
            ["settings"]
            ["clients"]
        )

        found = None

        for client in clients:

            if client.get("id") == uuid_value:

                found = client
                break

        if not found:
            return False

        # XHTTP_TLS: remove live user through Xray API.
        if kind == "XHTTP":

            email = found.get("email")

            if not email:
                return False

            ok, output = api_remove_user(
                kind,
                email
            )

            if not ok:
                print(
                    "DISABLE API REMOVE FAILED:",
                    output,
                    flush=True
                )
                return False

            clients.remove(found)

            valid, output = test_config_data(
                kind,
                data
            )

            if not valid:
                # Try to restore the live user if persistence validation fails.
                api_add_user(
                    kind,
                    data,
                    found
                )

                print(
                    "DISABLE TEST FAILED:",
                    output,
                    flush=True
                )
                return False

            save_config(
                kind,
                data
            )

            return True

        # Existing behavior for all other kinds.
        clients.remove(found)

        valid, output = test_config_data(kind, data)

        if not valid:
            print(
                "DISABLE TEST FAILED:",
                output,
                flush=True
            )
            return False

        save_config(
            kind,
            data
        )

        ok, output = restart_xray()

        if not ok:

            print(
                "DISABLE RESTART FAILED:",
                output,
                flush=True
            )

            return False

        return True

    except Exception as e:

        print(
            "DISABLE ERROR:",
            e,
            flush=True
        )

        return False



# =========================================================
# ENABLE USER
# =========================================================

def enable_user_in_xray(kind, uuid_value):

    conn = db()

    user = conn.execute(
        "SELECT * FROM users WHERE uuid=? AND kind=?",
        (uuid_value, kind)
    ).fetchone()

    conn.close()

    if not user:
        return False, "کاربر پیدا نشد."

    data = load_config(kind)

    clients = (
        inbound_of(data, kind)
        ["settings"]
        ["clients"]
    )

    for client in clients:

        if client.get("id") == uuid_value:

            return False, "کاربر از قبل فعال است."

    clients.append({
        "id": uuid_value,
        "email": user["email"]
    })

    valid, output = test_config_data(
        kind,
        data
    )

    if not valid:

        return False, output

    # XHTTP_TLS: add live user through Xray API without restart.
    if kind == "XHTTP":

        new_client = {
            "id": uuid_value,
            "email": user["email"]
        }

        ok, output = api_add_user(
            kind,
            data,
            new_client
        )

        if not ok:
            return False, output

        try:
            save_config(
                kind,
                data
            )
        except Exception as e:
            # Roll back the live API change if persistence fails.
            api_remove_user(
                kind,
                user["email"]
            )
            return False, str(e)

    else:

        save_config(
            kind,
            data
        )

        ok, output = restart_xray()

        if not ok:
            return False, output

    conn = db()

    conn.execute(
        """
        UPDATE users
        SET enabled=1,
            last_xray_bytes=0,
            updated_at=?
        WHERE uuid=?
          AND kind=?
        """,
        (
            datetime.now().isoformat(),
            uuid_value,
            kind
        )
    )

    conn.commit()
    conn.close()

    return True, "فعال شد."


# =========================================================

def format_server_address(address):
    """Format a direct IP for a URI; IPv6 needs brackets, IPv4 does not."""
    address = (address or "").strip()
    if ":" in address and not address.startswith("["):
        return f"[{address}]"
    return address


_CURVE_P = 2 ** 255 - 19


def _x25519_scalar_mult(scalar, u_bytes):
    """RFC 7748 X25519 with a fixed base point; pure Python so the installer needs no packages."""

    k = bytearray(scalar)
    k[0] &= 248
    k[31] &= 127
    k[31] |= 64

    scalar_int = int.from_bytes(k, "little")
    p = _CURVE_P

    x1 = int.from_bytes(u_bytes, "little") & ((1 << 255) - 1)
    x1 %= p

    x2, z2, x3, z3 = 1, 0, x1, 1
    swap = 0

    for bit in range(254, -1, -1):

        kt = (scalar_int >> bit) & 1
        swap ^= kt

        if swap:
            x2, x3 = x3, x2
            z2, z3 = z3, z2

        swap = kt

        a = (x2 + z2) % p
        aa = a * a % p
        b = (x2 - z2) % p
        bb = b * b % p
        e = (aa - bb) % p
        c = (x3 + z3) % p
        d = (x3 - z3) % p
        da = d * a % p
        cb = c * b % p

        x3 = (da + cb) ** 2 % p
        z3 = x1 * (da - cb) ** 2 % p
        x2 = aa * bb % p
        z2 = e * (aa + 121665 * e) % p

    if swap:
        x2, x3 = x3, x2
        z2, z3 = z3, z2

    return x2 * pow(z2, p - 2, p) % p


def x25519_public(private_key_b64):
    """The REALITY public key for a base64 private key, or "" when the key is unusable.

    v2ray-agent stores only `privateKey` in the inbound; a share link needs the public half,
    and the server never prints it in the config. Deriving it saves the user from pasting it.
    """

    try:
        raw = base64.b64decode(private_key_b64 or "", validate=True)
    except Exception:
        return ""

    if len(raw) != 32:
        return ""

    public = _x25519_scalar_mult(raw, (9).to_bytes(32, "little"))

    return base64.b64encode(public.to_bytes(32, "little")).decode("ascii")


def _transport_params(inbound, include_encryption=True):
    """Query parameters describing the transport, shared by the vless and trojan URIs."""

    stream = inbound.get("streamSettings") or {}
    network = stream.get("network", "tcp")
    security = stream.get("security", "none")

    params = [f"type={network}"]

    if include_encryption:
        params.append("encryption=none")

    if security == "reality":

        reality = stream.get("realitySettings") or {}
        server_names = reality.get("serverNames") or [""]
        short_ids = [s for s in (reality.get("shortIds") or []) if s]
        public_key = reality.get("publicKey") or x25519_public(reality.get("privateKey", ""))

        params += [
            "security=reality",
            "fp=chrome",
            f"pbk={quote(public_key, safe='')}",
            f"sid={quote(short_ids[0] if short_ids else '', safe='')}",
            f"sni={quote(server_names[0], safe='')}",
            f"spx={quote(reality.get('spiderX') or '/', safe='')}",
        ]

    elif security == "tls":

        tls = stream.get("tlsSettings") or {}
        params.append("security=tls")

        server_name = tls.get("serverName") or ""

        if server_name:
            params.append(f"sni={quote(server_name, safe='')}")

        alpn = tls.get("alpn") or []

        if alpn:
            params.append(f"alpn={quote(','.join(alpn), safe='')}")

    else:
        params.append("security=none")

    if network == "xhttp":

        xhttp = stream.get("xhttpSettings") or {}

        params += [
            f"path={quote(xhttp.get('path', ''), safe='')}",
            f"host={quote(xhttp.get('host', ''), safe='')}",
            f"mode={quote(xhttp.get('mode', 'auto'), safe='')}",
        ]

    elif network in ("ws", "httpupgrade"):

        ws = stream.get("wsSettings") or stream.get("httpupgradeSettings") or {}

        params += [
            f"path={quote(ws.get('path', ''), safe='')}",
            f"host={quote(ws.get('host', ''), safe='')}",
        ]

    elif network == "grpc":

        grpc = stream.get("grpcSettings") or {}
        params.append(f"serviceName={quote(grpc.get('serviceName', ''), safe='')}")

    elif network == "tcp":

        header = ((stream.get("tcpSettings") or {}).get("header") or {}).get("type")

        if header and header != "none":
            params.append(f"headerType={header}")

    return params


def _address_for(client):
    """The address to advertise: the one stored for the user, else any configured one."""

    raw = (
        client.get("server_ip")
        or SERVER_IP
        or (XHTTP_IPV6[0] if XHTTP_IPV6 else "")
    ).strip()

    if not raw:
        return None, None

    parsed = ipaddress.ip_address(raw)

    host = f"[{parsed.compressed}]" if parsed.version == 6 else str(parsed)

    return host, parsed


def make_v2rayng_link(kind, client):
    """A share link for the inbound `kind`, or None for a protocol this bot cannot describe."""

    entry = INBOUNDS.get(kind) or {}
    protocol = (entry.get("protocol") or "vless").lower()

    data = load_config(kind)
    inbound = inbound_of(data, kind)

    uuid_value = client.get("id") or client.get("password")
    email = client.get("email", "Xray")

    host, parsed = _address_for(client)

    if host is None:
        return None

    port = inbound.get("port") or entry.get("port") or XHTTP_PORT
    stream = inbound.get("streamSettings") or {}

    if protocol == "vless":

        params = _transport_params(inbound)
        flow = client.get("flow") or ""

        if flow:
            params.append(f"flow={quote(flow, safe='')}")

        query = "&".join(params)

        return f"vless://{uuid_value}@{host}:{port}?{query}#{quote(email, safe='')}"

    if protocol == "trojan":

        password = client.get("password") or uuid_value
        params = "&".join(_transport_params(inbound, include_encryption=False))

        return (
            f"trojan://{quote(password, safe='')}@{host}:{port}"
            f"?{params}#{quote(email, safe='')}"
        )

    if protocol == "vmess":

        network = stream.get("network", "tcp")
        security = stream.get("security", "none")

        host_header = ""
        path = ""

        if network == "xhttp":
            xhttp = stream.get("xhttpSettings") or {}
            host_header = xhttp.get("host", "")
            path = xhttp.get("path", "")
        elif network in ("ws", "httpupgrade"):
            ws = stream.get("wsSettings") or stream.get("httpupgradeSettings") or {}
            host_header = ws.get("host", "")
            path = ws.get("path", "")
        elif network == "grpc":
            path = (stream.get("grpcSettings") or {}).get("serviceName", "")

        payload = {
            "v": "2",
            "ps": email,
            "add": host.strip("[]"),
            "port": str(port),
            "id": uuid_value,
            "aid": str(client.get("alterId", 0)),
            "scy": "auto",
            "net": network,
            "type": "none",
            "host": host_header,
            "path": path,
            "tls": "tls" if security == "tls" else "",
        }

        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        return "vmess://" + base64.b64encode(raw).decode("ascii")

    return None


# =========================================================
# SEND CONFIG
# =========================================================

async def send_config_message(
    message,
    kind,
    client
):

    row = db_user(
        client["id"],
        kind
    )

    if row:
        if row["hostname"]:
            client["hostname"] = row["hostname"]

        if row["server_ip"]:
            client["server_ip"] = row["server_ip"]

    link = make_v2rayng_link(
        kind,
        client
    )

    if not link:

        await message.reply_text(
            "❌ برای این نوع اتصال لینک V2RayNG ساخته نشد."
        )

        return

    # فقط خود کانفیگ در این پیام قرار می‌گیرد.
    await message.reply_text(
        f"```\n{link}\n```",
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )


# =========================================================
# STATUS
# =========================================================

async def status(update, context):

    if not admin(update):
        return

    def run(cmd):

        try:

            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            ).stdout.strip()

        except:

            return "unknown"

    xray = run([
        "systemctl",
        "is-active",
        "xray"
    ])

    bot = run([
        "systemctl",
        "is-active",
        "xray-telegram-bot"
    ])

    uptime = run([
        "uptime",
        "-p"
    ])

    mem = run([
        "free",
        "-m"
    ])

    ram = "unknown"

    for line in mem.splitlines():

        if line.startswith("Mem:"):

            p = line.split()

            if len(p) >= 3:

                ram = (
                    f"{p[2]} MB / "
                    f"{p[1]} MB"
                )

    text = (
        "🖥 وضعیت سرور\n\n"
        f"Xray: {xray}\n"
        f"Bot: {bot}\n"
        f"RAM: {ram}\n"
        f"Uptime: {uptime}\n"
    )

    if update.callback_query:

        await update.callback_query.message.reply_text(
            text,
            reply_markup=back_keyboard()
        )

    else:

        await update.message.reply_text(
            text,
            reply_markup=back_keyboard()
        )


# =========================================================
# START
# =========================================================

async def start(update, context):

    if not admin(update):

        await denied(update)
        return

    await show_home(
        update,
        context
    )


async def help_cmd(update, context):

    if not admin(update):
        return

    await show_home(
        update,
        context
    )


# =========================================================
# HOME KEYBOARD
# =========================================================

def main_keyboard():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "➕ افزودن کاربر",
                callback_data="add"
            ),
            InlineKeyboardButton(
                "👥 کاربران",
                callback_data="list"
            )
        ],

        [
            InlineKeyboardButton(
                "🔐 کانفیگ",
                callback_data="configs"
            ),
            InlineKeyboardButton(
                "📊 مصرف",
                callback_data="usage"
            )
        ],

        [
            InlineKeyboardButton(
                "🗑 حذف",
                callback_data="delete"
            ),
            InlineKeyboardButton(
                "⛔ منقضی‌ها",
                callback_data="expired"
            )
        ],

        [
            InlineKeyboardButton(
                "🖥 وضعیت",
                callback_data="status"
            ),
            InlineKeyboardButton(
                "🔄 Restart",
                callback_data="restart"
            )
        ]
    ])


def back_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅️ منوی اصلی",
                callback_data="home"
            )
        ]
    ])


async def show_home(update, context):

    if not admin(update):
        return

    text = (
        "🤖 Xray Manager\n\n"
        "یک گزینه را انتخاب کنید:"
    )

    if update.callback_query:

        await update.callback_query.edit_message_text(
            text,
            reply_markup=main_keyboard()
        )

    else:

        await update.message.reply_text(
            text,
            reply_markup=main_keyboard()
        )



def api_remove_user(kind, email):
    """
    Remove one VLESS user from the already-running Xray
    through HandlerService/rmu. No Xray restart.
    """
    try:
        tag = INBOUNDS[kind]["tag"]

        result = subprocess.run(
            [
                XRAY_BIN,
                "api",
                "rmu",
                f"--server={XRAY_API}",
                f"-tag={tag}",
                email
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        output = (
            (result.stdout or "")
            + (result.stderr or "")
        ).strip()

        ok = (
            result.returncode == 0
            and "Removed 1 user(s) in total." in output
        )

        return ok, output

    except Exception as e:
        return False, str(e)


def api_add_user(kind, data, client):
    """
    Add one VLESS user to the already-running Xray through
    HandlerService/adu. No Xray restart.
    """
    import tempfile

    inbound = inbound_of(data, kind)

    api_data = {
        "inbounds": [
            {
                "port": inbound.get("port"),
                "listen": inbound.get("listen"),
                "protocol": inbound.get("protocol", "vless"),
                "settings": {
                    "clients": [client],
                    "decryption": inbound.get("settings", {}).get(
                        "decryption", "none"
                    )
                },
                "streamSettings": inbound.get(
                    "streamSettings", {}
                )
            }
        ]
    }

    # Keep optional fields when present.
    if "tag" in inbound:
        api_data["inbounds"][0]["tag"] = inbound["tag"]
    if "sniffing" in inbound:
        api_data["inbounds"][0]["sniffing"] = inbound["sniffing"]

    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="xray-adu-",
            delete=False,
            encoding="utf-8"
        ) as f:
            json.dump(api_data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            tmp_path = f.name

        result = subprocess.run(
            [
                XRAY_BIN,
                "api",
                "adu",
                f"--server={XRAY_API}",
                tmp_path
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        output = (result.stdout or "") + (result.stderr or "")

        ok = (
            result.returncode == 0
            and "Added 1 user(s) in total." in output
        )

        return ok, output.strip()

    except Exception as e:
        return False, str(e)

    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# =========================================================
# ADD USER
# =========================================================

async def add_user(
    update,
    context,
    kind,
    name
):

    if db_user_email(name):

        await update.message.reply_text(
            "❌ این نام قبلاً استفاده شده است."
        )

        return

    data = load_config(kind)

    clients = (
        inbound_of(data, kind)
        ["settings"]
        ["clients"]
    )

    for client in clients:

        if client.get("email") == name:

            await update.message.reply_text(
                "❌ این نام قبلاً در Xray وجود دارد."
            )

            return

    uuid_value = str(
        uuid.uuid4()
    )

    new_client = client_payload(kind, uuid_value, name)

    clients.append(new_client)

    valid, output = test_config_data(
        kind,
        data
    )

    if not valid:

        await update.message.reply_text(
            "❌ تست Xray ناموفق بود.\n\n"
            + output[-1500:]
        )

        return

    # Hot-add the new user to the running Xray.
    ok, output = api_add_user(
        kind,
        data,
        new_client
    )

    if not ok:

        await update.message.reply_text(
            "❌ افزودن کاربر به Xray ناموفق بود.\n\n"
            + output[-1500:]
        )

        return

    # Persist the configuration only after the live API add succeeds.
    try:
        save_config(
            kind,
            data
        )
    except Exception as e:
        await update.message.reply_text(
            "⚠️ کاربر در Xray اضافه شد اما ذخیره دائمی کانفیگ ناموفق بود.\n\n"
            + str(e)
        )
        return

    # -----------------------------------------------------
    # تعیین اطلاعات اختصاصی کاربر
    # -----------------------------------------------------

    hostname = None
    server_ip = None

    if kind == "XHTTP":
        server_ip = choose_xhttp_ipv6()

    # -----------------------------------------------------
    # ثبت فوری کاربر در DB
    # سهمیه فعلاً NULL است و بعداً UPDATE می‌شود.
    # -----------------------------------------------------

    try:

        create_db_user(
            uuid_value,
            name,
            kind,
            None,
            hostname,
            server_ip
        )

    except Exception as e:

        print(
            "DB CREATE ERROR:",
            e,
            flush=True
        )

        # اگر Xray ساخته شده ولی DB نشد، به کاربر اطلاع بده.
        await update.message.reply_text(
            "⚠️ کاربر در Xray ساخته شد اما ثبت در DB ناموفق بود.\n\n"
            "UUID:\n"
            f"{uuid_value}\n\n"
            "خطا:\n"
            f"{e}"
        )

        return

    # -----------------------------------------------------
    # context فقط برای custom quota و سازگاری نگه داشته می‌شود
    # -----------------------------------------------------

    context.user_data["new_uuid"] = uuid_value
    context.user_data["new_email"] = name
    context.user_data["new_kind"] = kind

    await update.message.reply_text(
        "📦 حجم کاربر را انتخاب کنید:",
        reply_markup=quota_keyboard(uuid_value)
    )


def quota_keyboard(uuid_value=None):

    def cb(value):
        if uuid_value:
            return f"quota:{value}:{uuid_value}"
        return f"quota:{value}"

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "20 GB",
                callback_data=cb("20")
            ),
            InlineKeyboardButton(
                "50 GB",
                callback_data=cb("50")
            )
        ],

        [
            InlineKeyboardButton(
                "100 GB",
                callback_data=cb("100")
            ),
            InlineKeyboardButton(
                "♾ نامحدود",
                callback_data=cb("unlimited")
            )
        ],

        [
            InlineKeyboardButton(
                "✏️ مقدار دلخواه",
                callback_data=cb("custom")
            )
        ]
    ])



async def text_name(update, context):

    if not admin(update):
        return

    if not context.user_data.get(
        "waiting_name"
    ):

        if context.user_data.get(
            "waiting_quota"
        ):

            await handle_custom_quota(
                update,
                context
            )

        return

    name = update.message.text.strip()

    if not re.match(r"^[A-Za-z0-9_.-]{1,32}$", name):

        await update.message.reply_text(
            "❌ نام نامعتبر است.\n"
            "نام را بدون فاصله وارد کنید."
        )

        return

    kind = context.user_data.get(
        "add_kind"
    )

    context.user_data["waiting_name"] = False
    context.user_data["add_kind"] = None

    await add_user(
        update,
        context,
        kind,
        name
    )


async def handle_custom_quota(
    update,
    context
):

    value = update.message.text.strip()

    try:

        gb = float(value)

        if gb <= 0 or gb > 1000000:

            raise ValueError

    except:

        await update.message.reply_text(
            "❌ مقدار نامعتبر است.\n"
            "مثلاً: 75"
        )

        return

    uuid_value = context.user_data.get(
        "new_uuid"
    )

    if not uuid_value:

        await update.message.reply_text(
            "❌ اطلاعات کاربر پیدا نشد.\n"
            "لطفاً دوباره کاربر را بسازید."
        )

        context.user_data.clear()

        return

    await finish_quota(
        update,
        context,
        quota_bytes_from_gb(gb),
        uuid_value
    )



async def finish_quota(
    update,
    context,
    quota,
    uuid_value=None
):

    # Normalize Update / Message
    message = (
        update.message
        if hasattr(update, "message")
        else update
    )

    if uuid_value is None:

        uuid_value = context.user_data.get(
            "new_uuid"
        )

    email = context.user_data.get(
        "new_email"
    )

    kind = context.user_data.get(
        "new_kind"
    )

    # اگر از callback آمده‌ایم، اطلاعات را از DB می‌گیریم.
    if uuid_value and (not email or not kind):

        row = db_user(
            uuid_value
        )

        if row:

            email = row["email"]
            kind = row["kind"]

    if not uuid_value or not email or not kind:

        await message.reply_text(
            "❌ اطلاعات کاربر پیدا نشد."
        )

        return

    # -----------------------------------------------------
    # کاربر باید قبلاً در DB ساخته شده باشد.
    # برای سازگاری با کاربران قدیمی، اگر نبود ایجادش می‌کنیم.
    # -----------------------------------------------------

    row = db_user(
        uuid_value,
        kind
    )

    if row:

        conn = db()

        conn.execute(
            """
            UPDATE users
            SET quota_bytes=?,
                updated_at=?
            WHERE uuid=?
              AND kind=?
            """,
            (
                quota,
                datetime.now().isoformat(),
                uuid_value,
                kind
            )
        )

        conn.commit()
        conn.close()

    else:

        # Compatibility fallback
        hostname = None
        server_ip = None

        if kind == "XHTTP":
            server_ip = choose_xhttp_ipv6()

        create_db_user(
            uuid_value,
            email,
            kind,
            quota,
            hostname,
            server_ip
        )

    # context را بعد از ثبت موفق پاک کن.
    context.user_data.clear()

    # اطلاعات را دوباره از DB می‌خوانیم تا IPv6/hostname
    # دقیقاً همان مقدار ذخیره‌شده باشد.
    row = db_user(
        uuid_value,
        kind
    )

    client = {
        "id": uuid_value,
        "email": email
    }

    if row:

        if row["hostname"]:
            client["hostname"] = row["hostname"]

        if row["server_ip"]:
            client["server_ip"] = row["server_ip"]

    await message.reply_text(
        "✅ کاربر ساخته شد\n\n"
        f"👤 Name: {email}\n"
        f"🔌 {INBOUNDS[kind]['name']}\n"
        f"📦 سهمیه: {quota_text(quota)}\n\n"
        "📱 کانفیگ V2RayNG:"
    )

    await send_config_message(
        message,
        kind,
        client
    )



# =========================================================
# CONFIG INFO
# =========================================================

async def send_config_info(
    message,
    kind,
    email
):

    data, client = find_client(
        kind,
        email
    )

    if not client:

        await message.reply_text(
            "❌ کاربر پیدا نشد."
        )

        return

    row = db_user(
        client["id"],
        kind
    )

    if row and row["hostname"]:
        client["hostname"] = row["hostname"]

    text = (
        "🔐 اطلاعات کاربر\n\n"
        f"👤 Name: {email}\n"
        f"🔌 نوع: {INBOUNDS[kind]['name']}\n"
        f"🆔 UUID: {client['id']}\n"
    )

    if row:

        text += (
            f"📦 سهمیه: "
            f"{quota_text(row['quota_bytes'])}\n"
            f"📊 مصرف: "
            f"{used_text(row['used_bytes'])}\n"
            f"📌 وضعیت: "
            f"{'🟢 فعال' if row['enabled'] else '🔴 غیرفعال'}\n"
        )

    await message.reply_text(text)

    await send_config_message(
        message,
        kind,
        client
    )


# =========================================================
# PERIODIC USAGE JOB
# =========================================================

async def usage_job(context):

    try:

        exceeded = collect_usage()

        for email, used, quota in exceeded or []:

            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    "⛔ سهمیه تمام شد و کاربر از Xray حذف شد\n"
                    f"👤 {email}\n"
                    f"📦 مصرف: {used_text(used)} از {used_text(quota)}\n"
                    "برای فعال‌سازی دوباره، سهمیه را افزایش دهید."
                )
            )

        print(
            "Usage collection completed.",
            flush=True
        )

    except Exception as e:

        print(
            "Hourly usage job error:",
            e,
            flush=True
        )


async def report_usage_job(context):
    try:
        conn = db()
        users = conn.execute(
            "SELECT email, kind, used_bytes, enabled FROM users ORDER BY email"
        ).fetchall()
        conn.close()

        if not users:
            text = "📊 گزارش مصرف کاربران\n\nهنوز کاربری ثبت نشده است."
        else:
            total = sum(int(u["used_bytes"] or 0) for u in users)
            active = sum(1 for u in users if u["enabled"])
            lines = [
                "📊 گزارش مصرف کاربران",
                f"🕒 زمان: {datetime.now(ZoneInfo('Asia/Baku')).strftime('%Y-%m-%d %H:%M')} (باکو)",
                f"👥 تعداد کاربران: {len(users)}",
                f"🟢 فعال: {active} | 🔴 غیرفعال: {len(users) - active}",
                f"📦 مجموع مصرف ثبت‌شده: {used_text(total)}",
                "",
                "جزئیات:"
            ]

            for u in users:
                status = "🟢" if u["enabled"] else "🔴"
                lines.append(
                    f"{status} {u['email']} | {u['kind']} | "
                    f"{used_text(u['used_bytes'] or 0)}"
                )

            text = "\n".join(lines)

        # Telegram messages have a maximum length.
        chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)]
        for chunk in chunks:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=chunk
            )

        print("Usage report sent to admin.", flush=True)

    except Exception as e:
        print("Usage report error:", e, flush=True)


# =========================================================
# BUTTONS
# =========================================================

async def buttons(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    if (
        not query.message
        or query.message.chat_id != ADMIN_CHAT_ID
    ):

        return

    data = query.data

    # HOME

    if data == "home":

        await show_home(
            update,
            context
        )

        return

    # ADD

    if data == "add":

        keyboard = InlineKeyboardMarkup([

            [
                InlineKeyboardButton(
                    "XHTTP / REALITY",
                    callback_data="add:XHTTP"
                )
            ],

            [
                InlineKeyboardButton(
                    "⬅️ بازگشت",
                    callback_data="home"
                )
            ]
        ])

        await query.message.reply_text(
            "➕ نوع اتصال را انتخاب کنید:",
            reply_markup=keyboard
        )

        return

    if data.startswith("add:"):

        kind = data.split(
            ":",
            1
        )[1]

        if kind not in INBOUNDS:

            return

        context.user_data.clear()

        context.user_data[
            "waiting_name"
        ] = True

        context.user_data[
            "add_kind"
        ] = kind

        await query.message.reply_text(
            f"➕ {INBOUNDS[kind]['name']}\n\n"
            "نام کاربر را وارد کنید:"
        )

        return

    # QUOTA

    if data.startswith("quota:"):

        parts = data.split(":")

        value = parts[1]

        uuid_value = (
            parts[2]
            if len(parts) >= 3
            else context.user_data.get("new_uuid")
        )

        if value == "custom":

            context.user_data[
                "waiting_quota"
            ] = True

            context.user_data[
                "new_uuid"
            ] = uuid_value

            # اطلاعات کاربر را از DB بازیابی کن
            row = db_user(uuid_value)

            if row:

                context.user_data[
                    "new_email"
                ] = row["email"]

                context.user_data[
                    "new_kind"
                ] = row["kind"]

            await query.message.reply_text(
                "📦 مقدار حجم را به GB وارد کنید:\n\n"
                "مثال:\n"
                "75"
            )

            return

        if value == "unlimited":

            quota = None

        else:

            try:

                quota = quota_bytes_from_gb(
                    float(value)
                )

            except ValueError:

                await query.message.reply_text(
                    "❌ مقدار حجم نامعتبر است."
                )

                return

        await finish_quota(
            query.message,
            context,
            quota,
            uuid_value
        )

        return

    # LIST

    if data == "list":

        clients = all_clients()

        if not clients:

            await query.message.reply_text(
                "👥 هیچ کاربری وجود ندارد.",
                reply_markup=back_keyboard()
            )

            return

        text = "👥 کاربران:\n\n"

        for i, client in enumerate(
            clients,
            1
        ):

            row = db_user(
                client["uuid"],
                client["kind"]
            )

            if row:

                quota = quota_text(
                    row["quota_bytes"]
                )

                used = used_text(
                    row["used_bytes"]
                )

                state = (
                    "🟢"
                    if row["enabled"]
                    else "🔴"
                )

                text += (
                    f"{i}. {state} "
                    f"{client['email']}\n"
                    f"   {client['kind']} | "
                    f"{used} / {quota}\n\n"
                )

            else:

                text += (
                    f"{i}. "
                    f"{client['email']}\n"
                    f"   {client['kind']}\n\n"
                )

        await query.message.reply_text(
            text,
            reply_markup=back_keyboard()
        )

        return

    # CONFIG MENU

    if data == "configs":

        clients = all_clients()

        if not clients:

            await query.message.reply_text(
                "هیچ کاربری وجود ندارد.",
                reply_markup=back_keyboard()
            )

            return

        keyboard = []

        for client in clients:

            keyboard.append([
                InlineKeyboardButton(
                    f"🔐 {client['email']}",
                    callback_data=(
                        f"config:"
                        f"{client['kind']}:"
                        f"{client['uuid']}"
                    )
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "⬅️ بازگشت",
                callback_data="home"
            )
        ])

        await query.message.reply_text(
            "🔐 کاربر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    if data.startswith("config:"):

        _, kind, uuid_value = data.split(
            ":",
            2
        )

        row = db_user(
            uuid_value,
            kind
        )

        if not row:

            await query.message.reply_text(
                "❌ کاربر در Database پیدا نشد."
            )

            return

        await send_config_info(
            query.message,
            kind,
            row["email"]
        )

        return

    # USAGE

    if data == "usage":

        conn = db()

        rows = conn.execute(
            """
            SELECT *
            FROM users
            ORDER BY email
            """
        ).fetchall()

        conn.close()

        if not rows:

            await query.message.reply_text(
                "📊 اطلاعات مصرفی وجود ندارد.",
                reply_markup=back_keyboard()
            )

            return

        text = "📊 مصرف کاربران\n\n"

        for row in rows:

            text += (
                f"👤 {row['email']}\n"
                f"🔌 {row['kind']}\n"
                f"📊 مصرف: "
                f"{used_text(row['used_bytes'])}\n"
                f"📦 سهمیه: "
                f"{quota_text(row['quota_bytes'])}\n"
                f"وضعیت: "
                f"{'🟢 فعال' if row['enabled'] else '🔴 غیرفعال'}\n\n"
            )

        await query.message.reply_text(
            text,
            reply_markup=back_keyboard()
        )

        return

    # DELETE

    if data == "delete":

        clients = all_clients()

        if not clients:

            await query.message.reply_text(
                "هیچ کاربری وجود ندارد.",
                reply_markup=back_keyboard()
            )

            return

        keyboard = []

        for client in clients:

            keyboard.append([
                InlineKeyboardButton(
                    f"🗑 {client['email']}",
                    callback_data=(
                        f"del:"
                        f"{client['kind']}:"
                        f"{client['uuid']}"
                    )
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "⬅️ بازگشت",
                callback_data="home"
            )
        ])

        await query.message.reply_text(
            "🗑 کاربر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    if data.startswith("del:"):

        _, kind, uuid_value = data.split(
            ":",
            2
        )

        row = db_user(
            uuid_value,
            kind
        )

        if not row:

            await query.message.reply_text(
                "❌ کاربر پیدا نشد."
            )

            return

        keyboard = InlineKeyboardMarkup([

            [
                InlineKeyboardButton(
                    "✅ بله، حذف شود",
                    callback_data=(
                        f"deleteyes:"
                        f"{kind}:"
                        f"{uuid_value}"
                    )
                )
            ],

            [
                InlineKeyboardButton(
                    "❌ لغو",
                    callback_data="home"
                )
            ]
        ])

        await query.message.reply_text(
            f"⚠️ حذف شود؟\n\n"
            f"👤 {row['email']}\n"
            f"📊 مصرف: "
            f"{used_text(row['used_bytes'])}",
            reply_markup=keyboard
        )

        return

    if data.startswith("deleteyes:"):

        _, kind, uuid_value = data.split(
            ":",
            2
        )

        row = db_user(
            uuid_value,
            kind
        )

        if not row:

            await query.message.reply_text(
                "❌ کاربر پیدا نشد."
            )

            return

        xdata = load_config(kind)

        clients = (
            inbound_of(xdata, kind)
            ["settings"]
            ["clients"]
        )

        target = None

        for client in clients:

            if client.get("id") == uuid_value:

                target = client
                break

        if target:

            clients.remove(target)

            valid, output = test_config_data(
                kind,
                xdata
            )

            if not valid:

                await query.message.reply_text(
                    "❌ تست Xray ناموفق بود.\n\n"
                    + output[-1500:]
                )

                return

            # XHTTP_TLS: remove live user without Xray restart.
            if kind == "XHTTP":

                email = target.get("email")

                ok, output = api_remove_user(
                    kind,
                    email
                )

                if not ok:

                    await query.message.reply_text(
                        "❌ حذف کاربر از Xray ناموفق بود.\n\n"
                        + output[-1000:]
                    )

                    return

                try:
                    save_config(
                        kind,
                        xdata
                    )
                except Exception as e:

                    # Try to restore the live user if persistence fails.
                    api_add_user(
                        kind,
                        xdata,
                        target
                    )

                    await query.message.reply_text(
                        "❌ حذف از فایل کانفیگ ناموفق بود.\n\n"
                        + str(e)
                    )

                    return

            else:

                save_config(
                    kind,
                    xdata
                )

                ok, output = restart_xray()

                if not ok:

                    await query.message.reply_text(
                        "❌ حذف انجام شد اما Xray "
                        "Restart نشد.\n\n"
                        + output[-1000:]
                    )

                    return

        remove_db_user(
            uuid_value,
            kind
        )

        await query.message.reply_text(
            f"✅ کاربر حذف شد:\n\n"
            f"👤 {row['email']}",
            reply_markup=back_keyboard()
        )

        return

    # EXPIRED

    if data == "expired":

        conn = db()

        rows = conn.execute(
            """
            SELECT *
            FROM users
            WHERE enabled=0
            """
        ).fetchall()

        conn.close()

        if not rows:

            await query.message.reply_text(
                "⛔ کاربر منقضی وجود ندارد.",
                reply_markup=back_keyboard()
            )

            return

        text = "⛔ کاربران غیرفعال\n\n"

        for row in rows:

            text += (
                f"👤 {row['email']}\n"
                f"📊 {used_text(row['used_bytes'])}"
                f" / "
                f"{quota_text(row['quota_bytes'])}\n\n"
            )

        await query.message.reply_text(
            text,
            reply_markup=back_keyboard()
        )

        return

    # STATUS

    if data == "status":

        await status(
            update,
            context
        )

        return

    # RESTART

    if data == "restart":

        await query.message.reply_text(
            "⏳ در حال Restart Xray..."
        )

        ok, output = restart_xray()

        await query.message.reply_text(
            "✅ Xray با موفقیت Restart شد."
            if ok
            else "❌ Restart ناموفق بود:\n"
            + output[-1500:],
            reply_markup=back_keyboard()
        )

        return


# =========================================================
# MAIN
# =========================================================

async def error_handler(update, context):

    print(
        "HANDLER ERROR:",
        context.error,
        flush=True
    )

    try:

        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                "⚠️ خطای داخلی ربات\n"
                f"{type(context.error).__name__}: {context.error}"
            )
        )

    except Exception:
        pass


def main():

    init_db()

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            help_cmd
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            buttons
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            text_name
        )
    )

    # Collect usage every 5 minutes; do not enforce volume quotas.
    if USAGE_MONITOR_ENABLED:
        app.job_queue.run_repeating(
            usage_job,
            interval=300,
            first=30
        )

        baku_tz = ZoneInfo("Asia/Baku")
        for hour in (0, 6, 12, 18):
            app.job_queue.run_daily(
                report_usage_job,
                time=datetime_time(hour=hour, minute=0, tzinfo=baku_tz),
                name=f"usage-report-{hour}"
            )

    print(
        "Xray Telegram Bot started.",
        flush=True
    )

    app.add_error_handler(error_handler)

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
