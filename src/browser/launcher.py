import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser.address_filter import AddressFilter
from browser.runtime import Chromium
from browser.scripts import BrowserScripts


def main() -> None:
    parser = argparse.ArgumentParser(description="Open the persistent browser")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--scripts", type=Path, required=True)
    parser.add_argument("--url", required=True)
    arguments = parser.parse_args()
    if arguments.url != "about:blank" and not AddressFilter("").allows(arguments.url):
        raise ValueError("Invalid browser URL")
    with sync_playwright() as runtime:
        context = runtime.chromium.launch_persistent_context(
            arguments.profile.resolve(),
            executable_path=Chromium().executable(),
            headless=False,
            chromium_sandbox=True,
            ignore_default_args=["--enable-automation"],
            timeout=15000,
        )
        try:
            BrowserScripts(arguments.scripts).configure(context)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(arguments.url, wait_until="domcontentloaded", timeout=30000)
            context.wait_for_event("close", timeout=0)
        finally:
            context.close()


if __name__ == "__main__":
    main()
