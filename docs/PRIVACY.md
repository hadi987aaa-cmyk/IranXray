# Privacy policy / سیاست حریم خصوصی

IranXray is a client for proxy protocols. It has no account, no analytics, no
advertising and no crash reporting. Nothing is sent to the developer.

IranXray یک کلاینت برای پروتکل‌های پروکسی است. حساب کاربری، تحلیل رفتار، تبلیغات و
گزارش خطا ندارد و هیچ داده‌ای برای توسعه‌دهنده ارسال نمی‌شود.

## What is stored on the device / چه چیزی روی گوشی ذخیره می‌شود

- Server profiles, subscription links, routing rules and app settings, kept in
  the app's private storage (MMKV). They never leave the device unless you
  export or share them yourself.
- Optional connection logs, kept in memory or the app's private storage, and
  removable from the log screen.

- پروفایل سرورها، لینک اشتراک‌ها، قواعد مسیریابی و تنظیمات، در حافظهٔ خصوصی اپ
  (MMKV) ذخیره می‌شوند و مگر خودتان خروجی بگیرید یا به اشتراک بگذارید، از گوشی
  بیرون نمی‌روند.
- گزارش اتصال (اختیاری) در حافظهٔ اپ نگه داشته می‌شود و از صفحهٔ گزارش‌ها قابل
  پاک‌کردن است.

## Network access / دسترسی شبکه

- The app connects only to the servers you add, plus the URLs you subscribe to.
- The update check asks the GitHub API for the latest release of this
  repository. It sends no identifier.
- Downloaded rule files and the Psiphon server list come from public GitHub
  repositories.

- اپ فقط به سرورهایی وصل می‌شود که خودتان اضافه کرده‌اید، به‌همراه آدرس‌های
  اشتراکی که ثبت می‌کنید.
- بررسی به‌روزرسانی، آخرین نسخهٔ همین مخزن را از GitHub API می‌پرسد و هیچ
  شناسه‌ای نمی‌فرستد.
- فایل‌های قواعد و فهرست سرورهای Psiphon از مخزن‌های عمومی GitHub گرفته می‌شوند.

Your traffic is encrypted between the device and the server you chose. The
operator of that server can see the metadata any proxy server sees; IranXray
itself keeps none of it.

## Permissions / دسترسی‌ها

`VpnService` (to route traffic), notifications (connection state), and network
access. Root mode uses superuser rights only when you enable it.

## Third-party components / اجزای شخص ثالث

The Xray core, Aether, psiphon-tunnel-core, lyrebird and hev-socks5-tunnel are
bundled under their own licenses, listed in the in-app open-source license
screen.

## Contact / تماس

Open an issue at <https://github.com/hadi987aaa-cmyk/IranXray/issues>.

_Last updated: 2026-11-11_
