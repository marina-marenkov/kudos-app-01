from __future__ import annotations

import argparse
import inspect
import sys
from collections.abc import Iterable
from typing import Any

from src import models


def _invoke_model(function_names: list[str], **kwargs: Any) -> Any:
    """Call the first existing DB-layer function with compatible kwargs."""
    for name in function_names:
        fn = getattr(models, name, None)
        if fn is None:
            continue

        signature = inspect.signature(fn)
        accepted_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key in signature.parameters
        }

        required = [
            param
            for param in signature.parameters.values()
            if param.default is inspect._empty
            and param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
        ]
        if any(param.name not in accepted_kwargs for param in required):
            continue

        return fn(**accepted_kwargs)

    names = ", ".join(function_names)
    raise RuntimeError(f"None of the DB functions were found/callable: {names}")


def _safe_rows(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, tuple):
        return list(payload)
    if isinstance(payload, Iterable) and not isinstance(payload, (str, bytes, dict)):
        return list(payload)
    if isinstance(payload, dict):
        for key in ("items", "rows", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return [payload]


def _extract_value(item: Any, keys: tuple[str, ...], default: str = "") -> str:
    if isinstance(item, dict):
        for key in keys:
            if key in item and item[key] is not None:
                return str(item[key])
    else:
        for key in keys:
            if hasattr(item, key):
                value = getattr(item, key)
                if value is not None:
                    return str(value)
    return default


def _cmd_give(args: argparse.Namespace) -> int:
    _invoke_model(["init_db"])
    record = _invoke_model(
        ["give_kudos", "create_kudos", "create_kudo", "add_kudos", "add_kudo"],
        from_user=args.from_user,
        to_user=args.to_user,
        message=args.msg,
        category=args.category,
        sender=args.from_user,
        recipient=args.to_user,
        msg=args.msg,
    )

    to_user = _extract_value(record, ("to_user", "recipient", "to", "receiver"), args.to_user)
    from_user = _extract_value(record, ("from_user", "sender", "from"), args.from_user)
    category = _extract_value(record, ("category",), args.category)
    message = _extract_value(record, ("message", "msg", "text"), args.msg)

    print("✅ Kudos recorded")
    print(f"From: {from_user}")
    print(f"To: {to_user}")
    print(f"Category: {category}")
    print(f"Message: {message}")
    return 0


def _cmd_leaderboard(_: argparse.Namespace) -> int:
    _invoke_model(["init_db"])
    results = _invoke_model(
        ["get_leaderboard", "leaderboard", "list_leaderboard", "fetch_leaderboard"]
    )
    rows = _safe_rows(results)

    if not rows:
        print("No kudos yet. Be the first to give one!")
        return 0

    print("🏆 Leaderboard")
    print("-" * 40)
    for idx, row in enumerate(rows, start=1):
        name = _extract_value(row, ("user", "username", "to_user", "recipient", "name"), "unknown")
        count = _extract_value(row, ("count", "kudos_count", "total", "score"), "0")
        print(f"{idx:>2}. {name:<20} {count}")
    return 0


def _cmd_recent(_: argparse.Namespace) -> int:
    _invoke_model(["init_db"])
    results = _invoke_model(["get_recent", "recent_kudos", "list_recent", "fetch_recent"])
    rows = _safe_rows(results)

    if not rows:
        print("No recent kudos.")
        return 0

    print("🕒 Recent kudos")
    print("-" * 60)
    for row in rows:
        from_user = _extract_value(row, ("from_user", "sender", "from"), "unknown")
        to_user = _extract_value(row, ("to_user", "recipient", "to"), "unknown")
        category = _extract_value(row, ("category",), "general")
        message = _extract_value(row, ("message", "msg", "text"), "")
        created = _extract_value(row, ("created_at", "timestamp", "created"), "")

        header = f"{from_user} → {to_user} [{category}]"
        if created:
            header = f"{header} ({created})"
        print(header)
        if message:
            print(f"  \"{message}\"")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kudos",
        description="Give kudos and view recognition stats from the local database.",
    )

    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        required=True,
        metavar="{give,leaderboard,recent}",
    )

    give_parser = subparsers.add_parser(
        "give",
        help="Give kudos to a teammate.",
        description="Record a kudos entry in the database.",
    )
    give_parser.add_argument(
        "--from",
        dest="from_user",
        required=True,
        metavar="USER",
        help="Sender username.",
    )
    give_parser.add_argument(
        "--to",
        dest="to_user",
        required=True,
        metavar="USER",
        help="Recipient username.",
    )
    give_parser.add_argument(
        "--msg",
        required=True,
        metavar="TEXT",
        help="Kudos message text.",
    )
    give_parser.add_argument(
        "--category",
        required=True,
        metavar="NAME",
        help="Recognition category, e.g. teamwork.",
    )
    give_parser.set_defaults(handler=_cmd_give)

    leaderboard_parser = subparsers.add_parser(
        "leaderboard",
        help="Show top recipients.",
        description="Display kudos leaderboard from local database.",
    )
    leaderboard_parser.set_defaults(handler=_cmd_leaderboard)

    recent_parser = subparsers.add_parser(
        "recent",
        help="Show recent kudos entries.",
        description="Display recently given kudos from local database.",
    )
    recent_parser.set_defaults(handler=_cmd_recent)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.handler(args)
    except Exception as exc:  # pragma: no cover
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
