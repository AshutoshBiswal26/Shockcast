"""Command-line entry point: `python -m shockcast.cli <command> --config <yaml>`."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from shockcast.config import load_config
from shockcast.db import SchemaMismatchError, check_schema, connect, init_db
from shockcast.ingest.m5 import M5FormatError, load_m5

log = logging.getLogger("shockcast")


def _cmd_init_db(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    init_db(cfg.data.db_path).close()
    print(f"Schema applied and verified: {cfg.data.db_path}")
    return 0


def _cmd_check_db(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    if not cfg.data.db_path.exists():
        print(f"Database does not exist: {cfg.data.db_path}", file=sys.stderr)
        return 1
    with connect(cfg.data.db_path) as con:
        problems = check_schema(con)
    if problems:
        print("Schema drift detected:\n  - " + "\n  - ".join(problems), file=sys.stderr)
        return 1
    print("Schema OK")
    return 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    with init_db(cfg.data.db_path) as con:
        if "m5" in args.sources:
            r = load_m5(con, cfg.data.m5_path, cfg.data.subsample_series, cfg.seed)
            print(
                f"M5: {r.n_series} series, {r.n_sales_rows} sales rows "
                f"({r.n_priced_rows} priced), {r.n_calendar_rows} calendar days "
                f"from {r.sales_file.name}"
            )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shockcast")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, func, help_ in (
        ("init-db", _cmd_init_db, "Create tables from db/schema.sql and verify"),
        ("check-db", _cmd_check_db, "Report drift between the DB and db/schema.sql"),
        ("ingest", _cmd_ingest, "Load data sources into DuckDB"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--config", default="configs/default.yaml")
        p.set_defaults(func=func)
        if name == "ingest":
            # Only M5 exists so far; exogenous sources arrive in task 2.3.
            p.add_argument("--sources", nargs="+", choices=["m5"], default=["m5"])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        rc: int = args.func(args)
        return rc
    except (SchemaMismatchError, M5FormatError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
