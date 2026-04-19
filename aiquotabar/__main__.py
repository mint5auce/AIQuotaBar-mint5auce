"""AI Quota Bar entry point."""

import multiprocessing
import sys


def main():
    # Required for multiprocessing 'spawn' inside a frozen py2app bundle —
    # child processes re-enter __main__ and would otherwise restart the app.
    multiprocessing.freeze_support()

    if len(sys.argv) > 1 and sys.argv[1] in ("--history", "-H"):
        from aiquotabar.history import cli_history
        cli_history()
    else:
        from aiquotabar.ui import AIQuotaBarApp
        AIQuotaBarApp().run()


if __name__ == "__main__":
    main()
