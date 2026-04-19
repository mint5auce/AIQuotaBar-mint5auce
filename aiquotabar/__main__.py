"""AI Quota Bar entry point."""

import json
import multiprocessing
import sys


def main():
    # Required for multiprocessing 'spawn' inside a frozen py2app bundle —
    # child processes re-enter __main__ and would otherwise restart the app.
    multiprocessing.freeze_support()

    argv = sys.argv[1:]

    if argv and argv[0] in ("--history", "-H"):
        from aiquotabar.history import cli_history
        cli_history()
    elif argv and argv[0] == "--detect-cookies":
        if len(argv) != 2:
            print(json.dumps({
                "status": "error",
                "error_type": "UsageError",
                "detail": "Usage: python -m aiquotabar --detect-cookies <provider_key>",
            }))
            sys.exit(2)
        from aiquotabar.providers import run_cookie_detection_cli
        sys.exit(run_cookie_detection_cli(argv[1]))
    else:
        from aiquotabar.ui import AIQuotaBarApp
        AIQuotaBarApp().run()


if __name__ == "__main__":
    main()
