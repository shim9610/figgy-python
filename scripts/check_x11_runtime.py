"""Fail before winit initialization when Linux X11 CI libraries are absent."""
import ctypes


LIBRARIES = {
    "libxkbcommon.so.0": "libxkbcommon0",
    "libxkbcommon-x11.so.0": "libxkbcommon-x11-0",
    "libX11.so.6": "libx11-6",
    "libvulkan.so.1": "libvulkan1",
}


def main():
    missing = []
    for library, package in LIBRARIES.items():
        try:
            ctypes.CDLL(library)
        except OSError as error:
            missing.append("%s (install %s): %s" % (library, package, error))
    if missing:
        raise SystemExit("Linux X11 runtime dependencies missing:\n" + "\n".join(missing))
    print("Linux X11 keyboard, window and Vulkan loader dependencies passed")


if __name__ == "__main__":
    main()
