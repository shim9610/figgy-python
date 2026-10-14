"""Select software GPUs for Linux CI native and Chromium WebGPU tests."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-icd", type=Path)
    parser.add_argument("--browser", type=Path)
    parser.add_argument("--browser-icd", type=Path)
    args = parser.parse_args()
    native = args.native_icd
    if native is None:
        candidates = sorted(Path("/usr/share/vulkan/icd.d").glob("lvp_icd*.json"))
        if not candidates:
            raise SystemExit("No Mesa lavapipe ICD; install mesa-vulkan-drivers for native CI")
        native = candidates[0]
    with sync_playwright() as playwright:
        browser = args.browser or Path(playwright.chromium.executable_path)
    if not browser.is_file():
        raise SystemExit("Chromium missing; run python -m playwright install --with-deps chromium")
    browser_icd = args.browser_icd
    if browser_icd is None:
        candidates = [browser.parent / "vk_swiftshader_icd.json",
                      browser.resolve().parent / "vk_swiftshader_icd.json"]
        browser_icd = next((p for p in candidates if p.is_file()), None)
    if browser_icd is None or not browser_icd.is_file() or not native.is_file():
        raise SystemExit("Software GPU ICD missing; Chromium must include its SwiftShader Vulkan ICD")
    for path in (native, browser_icd):
        if not json.loads(path.read_text()).get("ICD", {}).get("library_path"):
            raise SystemExit("Invalid Vulkan ICD: %s" % path)
    runtime = Path(tempfile.mkdtemp(prefix="figgyplot-ci-runtime-"))
    runtime.chmod(0o700)
    values = {"VK_DRIVER_FILES": str(native.resolve()),
              "FIGGY_BROWSER_VK_DRIVER": str(browser_icd.resolve()),
              "BROWSER_EXECUTABLE_PATH": str(browser.resolve()),
              "XDG_RUNTIME_DIR": str(runtime)}
    env_file = os.environ.get("GITHUB_ENV")
    if env_file:
        with Path(env_file).open("a", encoding="utf-8", newline="\n") as stream:
            for key, value in values.items():
                stream.write("%s=%s\n" % (key, value))
    print(json.dumps(values, indent=2))


if __name__ == "__main__":
    main()
