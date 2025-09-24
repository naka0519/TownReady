#!/usr/bin/env python3
"""Generate a TypeScript preset snippet from JSON input.

Usage:
  python scripts/register_preset.py preset.json > snippet.ts

The JSON format mirrors FacilityPreset in web/src/data/facilityPresets.ts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _quote(value: str) -> str:
    return f"'{value}'"


def _fmt_list(values: list[Any], indent: int = 0) -> str:
    pad = ' ' * indent
    if not values:
        return '[]'
    if all(isinstance(v, (int, float)) for v in values):
        return '[' + ', '.join(str(v) for v in values) + ']'
    if all(isinstance(v, str) for v in values):
        return '[' + ', '.join(_quote(v) for v in values) + ']'
    # nested objects
    parts = []
    for item in values:
        parts.append(_fmt_object(item, indent + 2))
    return '[\n' + ',\n'.join(parts) + f'\n{pad}]'


def _fmt_object(obj: dict[str, Any], indent: int = 0) -> str:
    pad = ' ' * indent
    inner_pad = ' ' * (indent + 2)
    lines: list[str] = ['{']
    for idx, (key, value) in enumerate(obj.items()):
        if isinstance(value, dict):
            lines.append(f"{inner_pad}{key}: {_fmt_object(value, indent + 2)},")
        elif isinstance(value, list):
            formatted = _fmt_list(value, indent + 2)
            if '\n' in formatted:
                lines.append(f"{inner_pad}{key}: {formatted},")
            else:
                lines.append(f"{inner_pad}{key}: {formatted},")
        elif isinstance(value, str):
            lines.append(f"{inner_pad}{key}: {_quote(value)},")
        elif isinstance(value, bool):
            lines.append(f"{inner_pad}{key}: {str(value).lower()},")
        elif value is None:
            lines.append(f"{inner_pad}{key}: undefined,")
        else:
            lines.append(f"{inner_pad}{key}: {value},")
    if lines[-1].endswith(','):
        lines[-1] = lines[-1][:-1]
    lines.append(pad + '}')
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert FacilityPreset JSON to TS snippet")
    parser.add_argument('json_file', type=Path, help='Path to preset JSON file')
    args = parser.parse_args()

    try:
        data = json.loads(args.json_file.read_text(encoding='utf-8'))
    except Exception as exc:  # pragma: no cover
        print(f'failed to read {args.json_file}: {exc}', file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict):
        print('Top-level JSON must be an object', file=sys.stderr)
        sys.exit(1)

    ts_snippet = _fmt_object(data, indent=2)
    preset_block = '  ' + ts_snippet.replace('\n', '\n  ') + ',\n'
    sys.stdout.write(preset_block)


if __name__ == '__main__':  # pragma: no cover
    main()
