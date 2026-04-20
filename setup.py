"""py2app build config for AIQuotaBar.

Build with:
    pip install py2app
    python3 setup.py py2app -A    # alias mode (fast iteration)
    python3 setup.py py2app       # frozen bundle for distribution

Output: dist/AIQuotaBar.app
"""

from setuptools import setup
from aiquotabar.version import get_display_version

APP = ["app.py"]

ICON_FILE = "assets/AIQuotaBar.icns"

DATA_FILES = [
    ("assets", [
        "assets/chatgpt_icon.png",
        "assets/chatgpt_icon_clean.png",
        "assets/claude_icon.png",
        "assets/copilot.png",
        "assets/cursor.png",
    ]),
]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": ICON_FILE,
    "plist": {
        "CFBundleIconFile": "AIQuotaBar.icns",
        "CFBundleName": "AIQuotaBar",
        "CFBundleDisplayName": "AIQuotaBar",
        "CFBundleIdentifier": "com.aiquotabar.app",
        "CFBundleShortVersionString": "1.7.0",
        "CFBundleVersion": "1.7.0",
        "AIQuotaBarBuildVersion": get_display_version(),
        "LSUIElement": True,
        "LSMinimumSystemVersion": "13.0",
        "NSHumanReadableCopyright": "MIT",
    },
    "packages": [
        "aiquotabar",
        "rumps",
        "curl_cffi",
        "browser_cookie3",
        "keyring",
    ],
    "includes": [
        "ServiceManagement",
    ],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
