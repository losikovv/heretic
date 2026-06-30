#!/usr/bin/env python3
from __future__ import annotations

import argparse

from build_static_site import add_static_build_arguments, build_from_args, print_build_result


def parse_args():
    parser = argparse.ArgumentParser(
        prog="builder",
        description="HereticTools build CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser(
        "build",
        help="Build the static HereticTools site.",
    )
    add_static_build_arguments(build_parser)

    return parser.parse_args()


def main():
    args = parse_args()
    if args.command == "build":
        print_build_result(build_from_args(args))
        return
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
