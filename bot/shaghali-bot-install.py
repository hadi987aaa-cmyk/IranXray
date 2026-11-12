#!/usr/bin/env python3
"""Install the Shaghali Telegram user-management bot on a server that already runs Xray.

The script adapts itself to whatever the server has: it finds the Xray binary, the config
directory and every VLESS/VMess/Trojan inbound that v2ray-agent created, enables the statistics
API when it is missing, and writes the bot's configuration from what it found.

Usage, on the server, as root:

    python3 shaghali-bot-install.py            # install or upgrade
    python3 shaghali-bot-install.py --check    # report only, change nothing
    python3 shaghali-bot-install.py --uninstall

Options: --conf-dir, --app-dir, --token, --admin-id, --no-service, --skip-telegram, --bot-file.
"""

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

CONF_CANDIDATES = [
    "/etc/v2ray-agent/xray/conf",
    "/usr/local/etc/v2ray-agent/xray/conf",
    "/etc/v2ray-agent/xray/conf.d",
    "/usr/local/etc/xray",
    "/etc/xray",
    "/etc/v2ray",
]

BIN_CANDIDATES = [
    "/usr/local/bin/xray",
    "/usr/bin/xray",
    "/usr/local/xray/xray",
    "/opt/xray/xray",
]

SKIP_FILES = ("routing", "outbounds", "log", "dns", "policy", "api", "balancer")

SUPPORTED_PROTOCOLS = ("vless", "vmess", "trojan")

API_FILE = "99_shaghali_api.json"
DEFAULT_API_PORT = 10085

BOT_VERSION = "21.6"

RAW_BOT_URL = (
    "https://raw.githubusercontent.com/hadi987aaa-cmyk/IranXray/bot/host/bot/bot_multi.py"
)


# --------------------------------------------------------------------------- helpers
def say(text):
    print(text, flush=True)


def run(cmd, check=False):
    """Run a command, returning (ok, stdout+stderr)."""
    try:
        done = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180, check=False
        )
        output = (done.stdout or "") + (done.stderr or "")
        if check and done.returncode != 0:
            raise SystemExit(f"command failed: {' '.join(cmd)}\n{output}")
        return done.returncode == 0, output
    except FileNotFoundError:
        return False, f"{cmd[0]}: not found"


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, payload):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


# --------------------------------------------------------------------------- detection
def detect_config_dir(explicit=None):
    if explicit:
        path = pathlib.Path(explicit)
        if not path.is_dir():
            raise SystemExit(f"--conf-dir {explicit} is not a directory")
        return path

    best, best_count = None, 0

    for candidate in CONF_CANDIDATES:
        path = pathlib.Path(candidate)
        if not path.is_dir():
            continue

        count = 0
        for item in path.glob("*.json"):
            try:
                payload = read_json(item)
            except Exception:
                continue
            if isinstance(payload, dict) and payload.get("inbounds"):
                count += len(payload["inbounds"])

        if count > best_count:
            best, best_count = path, count

    if best is None:
        raise SystemExit(
            "No Xray config directory with inbounds found. Tried: "
            + ", ".join(CONF_CANDIDATES)
            + "\nInstall v2ray-agent (or point --conf-dir at the directory holding the "
            "inbound json files)."
        )

    return best


def detect_xray_bin():
    found = shutil.which("xray")
    if found:
        return found

    for candidate in BIN_CANDIDATES:
        if pathlib.Path(candidate).is_file():
            return candidate

    return "xray"


def detect_api_port(conf_dir):
    """The port of the statistics API, or the default when the server has none yet."""
    for path in sorted(conf_dir.glob("*.json")):
        try:
            payload = read_json(path)
        except Exception:
            continue

        if not isinstance(payload, dict):
            continue

        api_tag = (payload.get("api") or {}).get("tag")

        for inbound in payload.get("inbounds") or []:
            if api_tag and inbound.get("tag") == api_tag:
                return int(inbound.get("port") or DEFAULT_API_PORT)

    return DEFAULT_API_PORT


def discover_inbounds(conf_dir):
    """Every user-facing inbound, as the registry the bot reads."""
    registry = {}

    for path in sorted(conf_dir.glob("*.json")):
        name = path.name.lower()

        if any(word in name for word in SKIP_FILES):
            continue

        try:
            payload = read_json(path)
        except Exception as error:
            say(f"  skip {path.name}: {error}")
            continue

        if not isinstance(payload, dict):
            continue

        for inbound in payload.get("inbounds") or []:
            protocol = (inbound.get("protocol") or "").lower()

            if protocol not in SUPPORTED_PROTOCOLS:
                continue

            clients = ((inbound.get("settings") or {}).get("clients")) or []

            if not isinstance(clients, list) or not clients:
                continue

            tag = inbound.get("tag") or f"{protocol}-{inbound.get('port')}"
            stream = inbound.get("streamSettings") or {}

            key = tag.lower().replace("/", "-").replace(" ", "-")

            registry[key] = {
                "file": path.name,
                "tag": tag,
                "name": pretty_name(protocol, stream),
                "protocol": protocol,
                "network": stream.get("network", "tcp"),
                "security": stream.get("security", "none"),
                "port": int(inbound.get("port") or 0),
            }

    return registry


NETWORK_LABELS = {
    "tcp": "TCP",
    "ws": "WebSocket",
    "xhttp": "XHTTP",
    "grpc": "gRPC",
    "h2": "HTTP/2",
    "httpupgrade": "HTTPUpgrade",
    "quic": "QUIC",
    "kcp": "mKCP",
}


def pretty_name(protocol, stream):
    network = NETWORK_LABELS.get((stream.get("network") or "tcp").lower(), stream.get("network") or "TCP")
    security = (stream.get("security") or "none").lower()
    security = {"reality": "Reality", "tls": "TLS"}.get(security, "")
    parts = [protocol.upper(), network] + ([security] if security else [])
    return " + ".join(parts)


def has_stats_api(conf_dir):
    for path in sorted(conf_dir.glob("*.json")):
        try:
            payload = read_json(path)
        except Exception:
            continue

        if not isinstance(payload, dict):
            continue

        api_tag = (payload.get("api") or {}).get("tag")

        if not api_tag:
            continue

        for inbound in payload.get("inbounds") or []:
            if inbound.get("tag") == api_tag and inbound.get("protocol") == "dokodemo-door":
                return True

    return False


# --------------------------------------------------------------------------- changes
def backup_conf_dir(conf_dir, app_dir):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = pathlib.Path("/root") / f"xray-conf-backup-{stamp}"

    if not pathlib.Path("/root").is_dir():
        target = app_dir / f"xray-conf-backup-{stamp}"

    shutil.copytree(conf_dir, target)
    return target


def ensure_stats_api(conf_dir, api_port):
    """Make sure Xray has the API + stats + policy that user traffic numbers need.

    v2ray-agent usually enables this for its own traffic display; when it is missing the bot
    can still add users, but cannot report usage or enforce quotas.
    """
    if has_stats_api(conf_dir):
        return False

    payload = {
        "api": {
            "tag": "api",
            "services": ["HandlerService", "LoggerService", "StatsService"],
        },
        "stats": {},
        "policy": {
            "levels": {"0": {"statsUserUplink": True, "statsUserDownlink": True}},
            "system": {
                "statsInboundUplink": True,
                "statsInboundDownlink": True,
                "statsOutboundUplink": True,
                "statsOutboundDownlink": True,
            },
        },
        "inbounds": [
            {
                "listen": "127.0.0.1",
                "port": api_port,
                "protocol": "dokodemo-door",
                "settings": {"address": "127.0.0.1"},
                "tag": "api",
            }
        ],
    }

    write_json(conf_dir / API_FILE, payload)
    return True


def detect_public_ip():
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            with urllib.request.urlopen(url, timeout=8) as response:
                value = response.read().decode().strip()
            if value:
                return value
        except Exception:
            continue

    return ""


def telegram(token, method, payload=None, timeout=30):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = None
    headers = {}

    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers)

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def ask_token(args):
    if args.token:
        return args.token.strip()

    say("")
    say("Telegram bot token (from @BotFather) — it is written to the .env file with 600 perms.")
    token = input("token: ").strip()

    if not token:
        raise SystemExit("no token given")

    return token


def verify_token(token):
    try:
        result = telegram(token, "getMe", timeout=15)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"Telegram rejected the token (HTTP {error.code}).") from error
    except Exception as error:
        raise SystemExit(f"Could not reach api.telegram.org: {error}") from error

    if not result.get("ok"):
        raise SystemExit(f"Telegram rejected the token: {result}")

    return result["result"].get("username", "")


def discover_admin_id(token, hint=None, wait_seconds=180):
    """The chat id of whoever sent /start to the bot while this waits."""
    if hint:
        return str(hint)

    say("")
    say("Open your bot in Telegram and press Start (or send /start).")
    say(f"Waiting up to {wait_seconds}s for the first message…")

    deadline = time.time() + wait_seconds
    seen_offset = None

    while time.time() < deadline:
        try:
            result = telegram(
                token, "getUpdates", {"offset": seen_offset, "timeout": 20}, timeout=30
            )
        except Exception:
            time.sleep(3)
            continue

        for update in result.get("result", []):
            seen_offset = update.get("update_id", 0) + 1
            message = (
                update.get("message")
                or update.get("edited_message")
                or update.get("callback_query", {}).get("message")
            )

            if not message:
                continue

            chat_id = (message.get("chat") or {}).get("id")

            if chat_id:
                say(f"  found chat id: {chat_id}")
                return str(chat_id)

        time.sleep(2)

    raise SystemExit(
        "No message arrived. Re-run with --admin-id <your numeric id> "
        "(send /start to @userinfobot to see it)."
    )


# --------------------------------------------------------------------------- install
def write_env(app_dir, values):
    env_path = app_dir / ".env"
    lines = [f"{key}={value}" for key, value in values.items()]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(env_path, 0o600)
    return env_path


def install_bot(app_dir, bot_source, registry, env_path, make_venv=True):
    shutil.copy2(bot_source, app_dir / "bot.py")
    write_json(app_dir / "inbounds.json", registry)

    venv = app_dir / "venv"

    if not make_venv:
        return venv

    if not (venv / "bin" / "python").exists():
        ok, output = run([sys.executable, "-m", "venv", str(venv)])
        if not ok:
            raise SystemExit(
                "Could not create a virtualenv.\n"
                + output
                + "\nOn Debian/Ubuntu: apt-get install -y python3-venv"
            )

    pip = str(venv / "bin" / "pip")
    ok, output = run([pip, "install", "--quiet", "--upgrade", "pip"])
    ok, output = run([pip, "install", "--quiet", f"python-telegram-bot=={BOT_VERSION}"])

    if not ok:
        raise SystemExit("pip install failed:\n" + output)

    return venv


UNIT = """[Unit]
Description=Shaghali Telegram bot (Xray user management)
After=network-online.target xray.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={app_dir}
EnvironmentFile={env_path}
ExecStart={venv}/bin/python {app_dir}/bot.py
Restart=always
RestartSec=5
LimitNOFILE=65535
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
"""


def install_service(app_dir, env_path, venv):
    unit = UNIT.format(app_dir=app_dir, env_path=env_path, venv=venv)
    path = pathlib.Path("/etc/systemd/system/shaghali-bot.service")

    path.write_text(unit, encoding="utf-8")

    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", "shaghali-bot"])

    return path


def self_test(app_dir, env_path, api_port, xray_bin):
    say("")
    say("checks")

    ok, output = run(["systemctl", "is-active", "xray"])
    say(f"  xray: {output.strip() or 'unknown'}")

    ok, output = run(["systemctl", "is-active", "shaghali-bot"])
    say(f"  shaghali-bot: {output.strip() or 'unknown'}")

    ok, output = run(
        [xray_bin, "api", "statsquery", f"--server=127.0.0.1:{api_port}"]
    )

    if ok and '"stat"' in output:
        names = output.count('"name"')
        say(f"  stats api: responding ({names} counters)")
    else:
        say("  stats api: NOT responding")
        say("    the bot can add users, but usage and quotas need the api inbound.")
        say(f"    last output: {output.strip()[:300]}")

    ok, output = run([str(app_dir / "venv" / "bin" / "python"), "-c", "import telegram; print(telegram.__version__)"])

    say(f"  python-telegram-bot: {output.strip() or 'missing'}")

    say("")
    say("logs:  journalctl -u shaghali-bot -n 40 --no-pager")


def uninstall(app_dir):
    run(["systemctl", "disable", "--now", "shaghali-bot"])
    unit = pathlib.Path("/etc/systemd/system/shaghali-bot.service")

    if unit.exists():
        unit.unlink()

    run(["systemctl", "daemon-reload"])
    say(f"service removed. Files left in {app_dir} (delete them yourself if you want).")


# --------------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report only, change nothing")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--conf-dir")
    parser.add_argument("--app-dir", default="/opt/shaghali-bot")
    parser.add_argument("--token")
    parser.add_argument("--admin-id")
    parser.add_argument("--no-service", action="store_true")
    parser.add_argument("--skip-telegram", action="store_true")
    parser.add_argument("--bot-file")
    parser.add_argument("--no-venv", action="store_true", help="skip venv/pip (detection tests)")
    parser.add_argument("--bot-url", default=RAW_BOT_URL)
    parser.add_argument("--server-ip")
    args = parser.parse_args()

    app_dir = pathlib.Path(args.app_dir)

    if args.uninstall:
        uninstall(app_dir)
        return

    say("== detection ==")
    conf_dir = detect_config_dir(args.conf_dir)
    say(f"  config dir: {conf_dir}")

    xray_bin = detect_xray_bin()
    say(f"  xray binary: {xray_bin}")

    api_port = detect_api_port(conf_dir)
    api_ready = has_stats_api(conf_dir)
    say(f"  stats api: {'port ' + str(api_port) if api_ready else 'missing (will be added)'}")

    registry = discover_inbounds(conf_dir)

    if not registry:
        raise SystemExit(
            "No VLESS/VMess/Trojan inbound with users was found in " + str(conf_dir)
        )

    say(f"  inbounds: {len(registry)}")

    for key, entry in registry.items():
        say(f"    - {key}: {entry['name']} on {entry['port']} ({entry['file']})")

    v2ray_agent = pathlib.Path("/etc/v2ray-agent").is_dir()
    say(f"  v2ray-agent: {'detected' if v2ray_agent else 'not detected'}")

    if args.check:
        say("")
        say("--check: nothing was written.")
        return

    say("")
    say("== prepare ==")
    app_dir.mkdir(parents=True, exist_ok=True)

    if not has_stats_api(conf_dir):
        backup = backup_conf_dir(conf_dir, app_dir)
        say(f"  backed up the config to {backup}")
        ensure_stats_api(conf_dir, api_port)
        say(f"  wrote {conf_dir / API_FILE} (api + stats + policy on 127.0.0.1:{api_port})")
        run(["systemctl", "restart", "xray"])
        time.sleep(2)

    server_ip = args.server_ip or detect_public_ip()
    say(f"  server address: {server_ip or 'unknown'}")

    token = ""
    admin_id = ""

    if not args.skip_telegram:
        say("")
        say("== telegram ==")
        token = ask_token(args)
        username = verify_token(token)
        say(f"  token ok: @{username}" if username else "  token ok")
        admin_id = discover_admin_id(token, args.admin_id)

    env_values = {
        "BOT_TOKEN": token,
        "ADMIN_CHAT_ID": admin_id,
        "SERVER_IP": server_ip,
        "XHTTP_IPV6": "",
        "XRAY_BIN": xray_bin,
        "XRAY_CONFIG_DIR": str(conf_dir),
        "XRAY_API": f"127.0.0.1:{api_port}",
        "XHTTP_PORT": str(next(iter(registry.values()))["port"]),
        "XHTTP_DIRECT_CONFIG": next(iter(registry.values()))["file"],
        "XHTTP_DIRECT_TAG": next(iter(registry.values()))["tag"],
        "BOT_APP_DIR": str(app_dir),
    }

    env_path = write_env(app_dir, env_values)
    say(f"  wrote {env_path} (600)")

    bot_source = pathlib.Path(args.bot_file) if args.bot_file else (
        pathlib.Path(__file__).parent / "bot_multi.py"
    )

    if not bot_source.is_file():
        say(f"  fetching the bot source from {args.bot_url}")
        target = app_dir / "bot_multi.py"

        try:
            with urllib.request.urlopen(args.bot_url, timeout=30) as response:
                target.write_bytes(response.read())
        except Exception as error:
            raise SystemExit(
                f"could not download the bot source ({error}).\n"
                "Copy bot_multi.py next to this script and pass --bot-file."
            ) from error

        bot_source = target

    venv = install_bot(app_dir, bot_source, registry, env_path, make_venv=not args.no_venv)
    say(f"  installed bot.py + inbounds.json, venv at {venv}")

    if not args.no_service:
        install_service(app_dir, env_path, venv)
        say("  service shaghali-bot enabled and started")
        time.sleep(3)
        self_test(app_dir, env_path, api_port, xray_bin)

    say("")
    say("done. Send /start to your bot in Telegram.")


if __name__ == "__main__":
    main()
