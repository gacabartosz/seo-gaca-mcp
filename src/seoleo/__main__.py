"""Entry point for `python -m seoleo` and `seoleo` CLI."""

from seoleo.server import mcp


def main():
    mcp.run()


if __name__ == "__main__":
    main()
