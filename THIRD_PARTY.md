# Third-party references

The Qt accessibility flag discovery approach in `src/qt_access.py` is adapted from the accessibility compatibility research in [wechatauto-replica](https://github.com/fanyuantaier/wechatauto-replica/blob/main/wechatauto/accessibility.py), licensed under Apache-2.0. The license is retained in `LICENSES/wechatauto-replica.txt`.

This project uses a narrow PE signature and category reference to locate the Qt runtime flag. It restores its own temporary change when monitoring stops and does not enable system screen-reader settings or use the upstream database-reading features.
