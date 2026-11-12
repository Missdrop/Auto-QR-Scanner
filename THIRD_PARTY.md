# Third-party references

The Qt accessibility flag discovery approach in `src/qt_access.py` is adapted from the accessibility compatibility research in [wechatauto-replica](https://github.com/fanyuantaier/wechatauto-replica/blob/main/wechatauto/accessibility.py), licensed under Apache-2.0. The license is retained in `LICENSES/wechatauto-replica.txt`.

The legacy UI adapter uses a narrow PE signature and category reference to locate the Qt runtime flag. It restores its own temporary change when monitoring stops and does not enable system screen-reader settings.

The default background adapter now uses the pinned `wechatauto-replica` database reader and cache-only media decoder. `src/image_keys.py` extends its read-only configuration discovery for the tested client, using the documented configuration layout and image-key derivation from upstream `db.py` and `media.py`. A candidate must match the bound account and decrypt the target image's probe before it is cached with Windows DPAPI. No UI download or sending API is used by this adapter.

The managed login storage reader uses Google's Apache-2.0 licensed [dfindexeddb](https://github.com/google/dfindexeddb) LevelDB parser, restricted to the application's own profile and the AMS `Token` / `userInfo` keys. The Windows dependency override selects the compatible prebuilt python-snappy package instead of its older native-build pin.

The independent Chromium runtime is installed using the locked Playwright package's official browser download. It is launched directly, without a Playwright automation connection, extensions or remote debugging. Runtime files and their bundled licenses remain outside Git in `.runtimes`.
