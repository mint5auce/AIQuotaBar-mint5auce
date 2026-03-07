"""AIQuotaBar entry point."""

import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--history", "-H"):
        from aiquotabar.history import cli_history
        cli_history()
    else:
        from aiquotabar.ui import ClaudeBar
        ClaudeBar().run()


if __name__ == "__main__":
    main()
