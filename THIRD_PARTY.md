# Third-party references

The Qt accessibility flag discovery approach in `src/qt_access.py` is adapted from the accessibility compatibility research in [wechatauto-replica](https://github.com/fanyuantaier/wechatauto-replica/blob/main/wechatauto/accessibility.py), licensed under Apache-2.0. The license is retained in `LICENSES/wechatauto-replica.txt`.

The legacy UI adapter uses a narrow PE signature and category reference to locate the Qt runtime flag. It restores its own temporary change when monitoring stops and does not enable system screen-reader settings.

The default background adapter now uses the pinned `wechatauto-replica` database reader and cache-only media decoder. `src/image_keys.py` extends its read-only configuration discovery for the tested client, using the documented configuration layout and image-key derivation from upstream `db.py` and `media.py`. A candidate must match the bound account and decrypt the target image's probe before it is cached with Windows DPAPI. No UI download or sending API is used by this adapter.

The managed login storage reader uses Google's Apache-2.0 licensed [dfindexeddb](https://github.com/google/dfindexeddb) LevelDB parser, restricted to the application's own profile and the AMS `Token` / `userInfo` keys. The Windows dependency override selects the compatible prebuilt python-snappy package instead of its older native-build pin.

The PowerShell startup script downloads [uv](https://github.com/astral-sh/uv) from its official release, pinned by URL, size and SHA-256 in `scripts/uv.json`. Downloaded runtimes remain outside Git. The zstd override selects a release with Python 3.12 Windows wheels so setup does not require a native compiler.

The independent browser is an unbranded Chromium build from the [official Chromium snapshot archive](https://www.chromium.org/getting-involved/download-chromium/). Its revision, archive URL, size and official object MD5 metadata are pinned in `src/chromium.json`. Installation verifies the archive, and startup verifies the installed executable's recorded SHA-256. Login launches it directly. Background QR processing uses [Playwright](https://github.com/microsoft/playwright-python), licensed under Apache-2.0, with this same executable and the application's dedicated persistent profile. Playwright connects through its private browser pipe; no debugging TCP port or browser extension is installed. Runtime files and their bundled licenses remain outside Git in `.runtimes`.

The SQLite login reader follows the storage layout documented in Chromium's [LocalStorageSqlite](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/services/storage/dom_storage/sqlite/local_storage_sqlite.h). Zstandard values are decoded with bounded output. Only the managed profile's AMS session entries are selected.
