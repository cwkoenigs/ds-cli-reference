"""Entry point: importing the command modules registers them on the Typer app."""
from .config import app  # noqa: F401
from .commands import agent, canon, new, setup  # noqa: F401


def main():
    app()


if __name__ == "__main__":
    main()
