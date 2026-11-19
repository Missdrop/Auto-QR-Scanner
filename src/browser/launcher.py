import argparse
import subprocess
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

from browser.address_filter import AddressFilter
from browser.runtime import Chromium
from browser.scripts import BrowserScripts


def profile_is_busy(message: str) -> bool:
    return any(
        marker in message
        for marker in (
            "ProcessSingleton",
            "Opening in existing browser session",
            "user data directory is already in use",
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Open the persistent browser")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--scripts", type=Path, required=True)
    parser.add_argument("--url", required=True)
    arguments = parser.parse_args()
    if arguments.url != "about:blank" and not AddressFilter("").allows(arguments.url):
        raise ValueError("Invalid browser URL")
    with sync_playwright() as runtime:
        executable = Chromium().executable()
        try:
            context = runtime.chromium.launch_persistent_context(
                arguments.profile.resolve(),
                executable_path=executable,
                headless=False,
                chromium_sandbox=True,
                ignore_default_args=["--enable-automation"],
                timeout=15000,
            )
        except Error as exception:
            if not profile_is_busy(str(exception)):
                raise
            # Another application instance may already own this exact profile.
            # Let Chromium forward the URL without starting a second owner.
            subprocess.run(
                [
                    str(executable),
                    "--user-data-dir=" + str(arguments.profile.resolve()),
                    "--new-window",
                    arguments.url,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=True,
                timeout=10,
            )
            return
        try:
            BrowserScripts(arguments.scripts).configure(context)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(arguments.url, wait_until="domcontentloaded", timeout=30000)
            context.wait_for_event("close", timeout=0)
        finally:
            context.close()


if __name__ == "__main__":
    main()
