"""Entry point for `python -m gaca` and `gaca` CLI."""

from gaca.server import mcp


def main():
    mcp.run()


if __name__ == "__main__":
    main()
