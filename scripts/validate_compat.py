#!/usr/bin/env python3
"""validate_compat.py — three-layer validator for compatibility.yaml.

Pipeline:
    L1 (yaml.safe_load)
      -> exit 3 on syntax error
    L2 (jsonschema against compatibility.schema.yaml)
      -> exit 4 on schema violation
    L3 (semantic rules, see data-model.md "Validation Rules Summary")
      -> exit 5 on rule violation

All three layers green -> exit 0 and print 'manifest OK'.

Consumed by:
    .github/workflows/zmk-main-compat.yml  (validate-manifest job)
    Makefile / release workflow            (pre-tag check)
    pre-commit hook (optional)             (file-change guard)

Contract: specs/003-zmk-revision-pinning/contracts/compatibility-yaml-schema.md
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError as e:  # pragma: no cover - fail-closed when dep missing
    print(f"error: pyyaml not available ({e}); install via scripts/requirements-dev.txt", file=sys.stderr)
    sys.exit(2)

try:
    import jsonschema
except ImportError as e:  # pragma: no cover
    print(f"error: jsonschema not available ({e}); install via scripts/requirements-dev.txt", file=sys.stderr)
    sys.exit(2)


EXIT_OK = 0
EXIT_USAGE = 2
EXIT_L1_SYNTAX = 3
EXIT_L2_SCHEMA = 4
EXIT_L3_SEMANTIC = 5


def layer_1_yaml_load(path: Path) -> dict:
    """L1: yaml.safe_load with precise error reporting."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError:
        print(f"error [L1]: compatibility file not found: {path}", file=sys.stderr)
        sys.exit(EXIT_L1_SYNTAX)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        loc = f"line {mark.line + 1} col {mark.column + 1}" if mark else "unknown location"
        print(f"error [L1 YAML syntax] at {loc}: {exc}", file=sys.stderr)
        sys.exit(EXIT_L1_SYNTAX)

    if not isinstance(data, dict):
        print(f"error [L1]: root of {path} must be a mapping, got {type(data).__name__}", file=sys.stderr)
        sys.exit(EXIT_L1_SYNTAX)
    return data


def layer_2_schema(data: dict, schema_path: Path) -> None:
    """L2: jsonschema against compatibility.schema.yaml."""
    try:
        with schema_path.open("r", encoding="utf-8") as fh:
            schema = yaml.safe_load(fh)
    except (FileNotFoundError, yaml.YAMLError) as exc:
        print(f"error [L2]: schema unreadable at {schema_path}: {exc}", file=sys.stderr)
        sys.exit(EXIT_L2_SCHEMA)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        for err in errors:
            pointer = "/" + "/".join(str(p) for p in err.absolute_path) if err.absolute_path else "/"
            print(f"error [L2 schema] at {pointer}: {err.message}", file=sys.stderr)
        sys.exit(EXIT_L2_SCHEMA)


def _find_call_in_file(file_path: Path, candidates: list[str]) -> str | None:
    """Grep candidates in the given .c/.h file. Returns the hit name or None."""
    if not file_path.exists():
        return None
    text = file_path.read_text(encoding="utf-8", errors="replace")
    for name in candidates:
        if re.search(rf"\b{re.escape(name)}\s*\(", text):
            return name
    return None


def layer_3_semantic(
    data: dict,
    module_root: Path,
    zmk_root: Path | None,
    check_git_tag: bool,
) -> None:
    """L3: semantic rules per data-model.md "Validation Rules Summary"."""
    errors: list[str] = []

    # Rule 1: required_symbols[i].name globally unique
    names = [s["name"] for s in data["required_symbols"]]
    dups = {n for n in names if names.count(n) > 1}
    if dups:
        errors.append(f"[L3 rule 1] duplicate required_symbols[].name: {sorted(dups)}")

    # Rule 2: emits_macro globally unique (ignoring unset)
    macros = [s["emits_macro"] for s in data["required_symbols"] if "emits_macro" in s]
    dup_macros = {m for m in macros if macros.count(m) > 1}
    if dup_macros:
        errors.append(f"[L3 rule 2] duplicate emits_macro: {sorted(dup_macros)}")

    # Rule 3: module_version matches `git describe --exact-match` (opt-in)
    if check_git_tag:
        try:
            tag = subprocess.check_output(
                ["git", "-C", str(module_root), "describe", "--exact-match", "--tags", "HEAD"],
                stderr=subprocess.STDOUT,
                text=True,
            ).strip()
            # strip leading 'v' if any
            tag_version = tag[1:] if tag.startswith("v") else tag
            if tag_version != data["module_version"]:
                errors.append(
                    f"[L3 rule 3] module_version={data['module_version']} but current git tag={tag}"
                )
        except subprocess.CalledProcessError as exc:
            errors.append(
                f"[L3 rule 3] --check-git-tag requested but HEAD is not an exact tag: {exc.output.strip()}"
            )

    # Rule 4: each required_symbols[i].used_in must grep-hit name or any fallback
    for i, sym in enumerate(data["required_symbols"]):
        used_in = module_root / sym["used_in"]
        candidates = [sym["name"], *sym.get("fallback", [])]
        hit = _find_call_in_file(used_in, candidates)
        if hit is None:
            errors.append(
                f"[L3 rule 4] required_symbols[{i}]={sym['name']}: no call site found in {used_in} "
                f"(tried: {candidates})"
            )

    # Rule 5: known_good.lower/upper must be real ZMK commits (opt-in on zmk_root)
    if zmk_root is not None:
        for key in ("lower", "upper"):
            sha = data["zmk_known_good"].get(key)
            if sha is None:
                continue
            rc = subprocess.call(
                ["git", "-C", str(zmk_root), "cat-file", "-e", f"{sha}^{{commit}}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if rc != 0:
                errors.append(
                    f"[L3 rule 5] zmk_known_good.{key}={sha} not found in ZMK repo at {zmk_root}"
                )

    # Rule 6: escape_hatch.kconfig symbol must be declared in Kconfig.keybeacon
    hatch_name = data["escape_hatch"]["kconfig"]
    # hatch_name 形如 CONFIG_ZMK_KEYBEACON_ALLOW_INCOMPATIBLE_ZMK；Kconfig 文件里声明为 ZMK_KEYBEACON_ALLOW_INCOMPATIBLE_ZMK
    kconfig_symbol = hatch_name.removeprefix("CONFIG_")
    kconfig_file = module_root / "Kconfig.keybeacon"
    if kconfig_file.exists():
        kc_text = kconfig_file.read_text(encoding="utf-8", errors="replace")
        if not re.search(rf"^\s*config\s+{re.escape(kconfig_symbol)}\s*$", kc_text, re.MULTILINE):
            errors.append(
                f"[L3 rule 6] escape_hatch.kconfig={hatch_name} but 'config {kconfig_symbol}' "
                f"not declared in {kconfig_file}"
            )
    else:
        errors.append(f"[L3 rule 6] Kconfig.keybeacon not found at {kconfig_file}")

    if errors:
        for e in errors:
            print(f"error {e}", file=sys.stderr)
        sys.exit(EXIT_L3_SEMANTIC)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--compat-file",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "compatibility.yaml",
        help="Path to compatibility.yaml (default: <module root>/compatibility.yaml)",
    )
    parser.add_argument(
        "--schema-file",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "compatibility.schema.yaml",
        help="Path to compatibility.schema.yaml",
    )
    parser.add_argument(
        "--zmk-root",
        type=Path,
        default=None,
        help="Path to a ZMK repo clone; enables L3 rule 5 (known_good sha existence check)",
    )
    parser.add_argument(
        "--check-git-tag",
        action="store_true",
        help="Enable L3 rule 3 (module_version must match current git tag). Only use at release time.",
    )
    args = parser.parse_args()

    compat_path: Path = args.compat_file.resolve()
    schema_path: Path = args.schema_file.resolve()
    module_root: Path = compat_path.parent

    # L1
    data = layer_1_yaml_load(compat_path)
    # L2
    layer_2_schema(data, schema_path)
    # L3
    layer_3_semantic(
        data,
        module_root=module_root,
        zmk_root=args.zmk_root.resolve() if args.zmk_root else None,
        check_git_tag=args.check_git_tag,
    )

    print("manifest OK")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
