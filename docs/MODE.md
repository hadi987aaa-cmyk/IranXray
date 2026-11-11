# Run modes / حالت‌های اجرا

IranXray can move traffic in three ways. Pick the first one unless you know
why you need another.

## 1. VPN (default) / حالت VPN

The app runs Android's `VpnService` and creates a local TUN interface. Every app
that talks to the internet is routed through it, so nothing has to be
configured per app. Android shows the VPN key icon while it runs.

- Use it for normal browsing, messengers and every app that ignores proxy
  settings.
- Routing rules (direct for Iranian sites, proxy for the rest) and per-app
  routing apply in this mode.
- Turning off the notification from the system may let Android kill the
  service; keep the ongoing notification.

اپ با `VpnService` یک رابط TUN محلی می‌سازد و ترافیک همهٔ برنامه‌ها را از آن رد
می‌کند؛ لازم نیست هیچ اپی را جداگانه تنظیم کنید. تا وقتی وصل هستید، آیکون کلید
VPN در نوار وضعیت دیده می‌شود. قواعد مسیریابی و «پروکسی برای هر اپ» فقط در همین
حالت کار می‌کنند.

## 2. Proxy only / فقط پروکسی

The core listens on a local SOCKS/HTTP port (default `127.0.0.1:10808`) and
nothing is intercepted automatically. Apps must be pointed at that proxy
themselves.

- Useful on devices where creating a VPN is refused, or when you only want one
  browser or tool to use the tunnel.
- No system-wide routing rules and no per-app routing.

هسته فقط روی یک پورت محلی (پیش‌فرض `127.0.0.1:10808`) گوش می‌دهد و هیچ ترافیکی
خودکار گرفته نمی‌شود؛ باید خودتان در برنامهٔ موردنظر پروکسی را تنظیم کنید.
مناسب دستگاه‌هایی که اجازهٔ ساخت VPN نمی‌دهند یا وقتی فقط یک برنامه را می‌خواهید
از تونل رد کنید.

## 3. Root mode / حالت روت

With superuser rights the app redirects traffic with `TPROXY` instead of
`VpnService`. The VPN key icon disappears and per-app routing and VPN-related
settings no longer apply.

- Only for rooted devices; a wrong rule can break connectivity until reboot.
- Handy when the ROM blocks `VpnService`, or for tethering scenarios.

با دسترسی روت، ترافیک با `TPROXY` هدایت می‌شود نه `VpnService`؛ آیکون VPN نمی‌آید
و تنظیمات مربوط به VPN و «پروکسی برای هر اپ» بی‌اثر می‌شوند. فقط برای دستگاه روت
شده مناسب است.

## Notes for Iranian networks / نکته‌ها برای شبکهٔ ایران

- Most apps ignore manual proxy settings, so **VPN mode** is the practical
  choice.
- If a connection drops when the phone switches between Wi-Fi and mobile data,
  the app reloads the core on the new network by itself; if it does not
  recover, tap disconnect and connect again.
- Latency shown by the delay test is measured against `www.bing.com` and
  `www.wikipedia.org`, chosen because Google endpoints are blocked here.
- A server behind the Cloudflare orange cloud needs its own port
  (`2053`, `2083`, `2087`, `2096`, `8443`) and a DNS-over-HTTPS resolver; if the
  handshake still resets, the path is blocked and only a different server or a
  different front helps.
