"""Run storage initialization: python -m storage <database-path>."""

import argparse

from .db import init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the canonical DuckDB storage")
    parser.add_argument("database", help="DuckDB file to initialize")
    init_db(parser.parse_args().database)


if __name__ == "__main__":
    main()
