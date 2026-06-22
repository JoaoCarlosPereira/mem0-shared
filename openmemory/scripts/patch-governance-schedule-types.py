#!/usr/bin/env python3
"""Fix Pydantic forward-ref issue: List[int] -> list[int] under __future__ annotations."""

from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "api" / "app" / "routers" / "governance_schedule.py"


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if "list[int]" in text and "from typing import List" not in text:
        print(f"Already patched: {TARGET}")
        return
    text = text.replace("from typing import List\n\n", "")
    text = text.replace("List[int]", "list[int]")
    TARGET.write_text(text, encoding="utf-8")
    print(f"Patched {TARGET}")


if __name__ == "__main__":
    main()
