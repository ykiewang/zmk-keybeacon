#!/usr/bin/env python3
"""regen_ci.py — derive .github/workflows/zmk-main-compat.yml from
compatibility.yaml:ci so the single source of truth stays authoritative.

Flow:
    compatibility.yaml:ci   -->  regen_ci.py (this)  -->  zmk-main-compat.yml

Modes:
    (default)  —  overwrite the workflow file in place
    --check    —  render to memory and byte-diff against the on-disk file;
                  exit 1 if drift, 0 if clean (for CI validate-manifest job
                  and pre-commit hooks)

Contract: specs/003-zmk-revision-pinning/contracts/ci-workflow-contract.md
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

try:
    import yaml
except ImportError as e:  # pragma: no cover
    print(f"error: pyyaml not available ({e})", file=sys.stderr)
    sys.exit(2)


HEADER = """\
# ⚠️ 此文件由 scripts/regen_ci.py 从 compatibility.yaml 派生，请勿手改。
# To update, edit compatibility.yaml and run: python3 scripts/regen_ci.py
# CI's validate-manifest job also runs `python3 scripts/regen_ci.py --check`.
#
# Contract: specs/003-zmk-revision-pinning/contracts/ci-workflow-contract.md

name: ZMK main-HEAD compat matrix

on:
  schedule:
    - cron: "{schedule}"
  workflow_dispatch:
  pull_request:
    paths:
      - compatibility.yaml
      - cmake/zmk_compat.cmake
      - scripts/check_zmk_compat.py
      - scripts/validate_compat.py
      - scripts/regen_ci.py
      - scripts/update-readme-table.py
      - scripts/tests/**
      - scripts/requirements-dev.txt
      - .github/workflows/zmk-main-compat.yml
      - keybeacon.c
      - Kconfig.keybeacon

jobs:
  validate-manifest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          # fetch-depth: 0 is required so that `scripts/update-readme-table.py`
          # can enumerate all historical v* tags via `git for-each-ref` when
          # the pytest suite exercises its --check mode. A shallow clone drops
          # the pre-v1.1.4 rows and makes the check report a false drift.
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r scripts/requirements-dev.txt
      - run: python3 scripts/validate_compat.py
      - run: python3 scripts/regen_ci.py --check
      - run: python3 -m pytest scripts/tests/

  build:
    needs: validate-manifest
    runs-on: ubuntu-latest
    container:
      image: zmkfirmware/zmk-dev-arm:3.5
    strategy:
      fail-fast: false
      matrix:
        zmk_ref: {zmk_refs}
        shield:  {shields}
    steps:
      - uses: actions/checkout@v4
        with:
          path: zmk-keybeacon
      - uses: actions/checkout@v4
        with:
          repository: zmkfirmware/zmk
          ref: ${{{{ matrix.zmk_ref }}}}
          path: zmk
      - name: Resolve ZMK sha
        id: zmksha
        run: echo "sha=$(git -C zmk rev-parse HEAD)" >> $GITHUB_OUTPUT
      - name: west init + update
        working-directory: zmk
        run: |
          west init -l app
          west update --narrow -o=--depth=1
          west zephyr-export
      - name: west build (ZMK ref=${{{{ matrix.zmk_ref }}}}, shield=${{{{ matrix.shield }}}})
        working-directory: zmk
        # CONFIG_ZMK_KEYBEACON=y is required to actually link our C sources —
        # otherwise keybeacon.cmake's zephyr_library() guard short-circuits
        # and we never prove that keybeacon.c compiles against this ZMK ref.
        # The compat probe runs regardless (it's at include() time, above the
        # Kconfig guard), but we want the C-level verification too.
        run: |
          west build -s app -d build -b xiao_ble -- \
            -DSHIELD=${{{{ matrix.shield }}}} \
            -DZMK_EXTRA_MODULES=${{{{ github.workspace }}}}/zmk-keybeacon \
            -DCONFIG_ZMK_KEYBEACON=y
      - name: Upload build log on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: build-log-${{{{ matrix.zmk_ref }}}}-${{{{ matrix.shield }}}}
          path: |
            zmk/build/CMakeFiles/CMakeConfigureLog.yaml
            zmk/build/zephyr/.config
          retention-days: 30

  file-issue-on-main-break:
    needs: build
    if: failure() && github.event_name == 'schedule'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/github-script@v7
        with:
          script: |
            const existing = await github.rest.issues.listForRepo({{
              owner: context.repo.owner,
              repo: context.repo.repo,
              state: 'open',
              labels: '{issue_label}'
            }});
            if (existing.data.length > 0) {{
              core.info(`existing compat-break issue #${{existing.data[0].number}}, skip.`);
              return;
            }}
            const today = new Date().toISOString().slice(0, 10);
            const runUrl = `${{context.serverUrl}}/${{context.repo.owner}}/${{context.repo.repo}}/actions/runs/${{context.runId}}`;
            await github.rest.issues.create({{
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `[compat] ZMK matrix failed on ${{today}}`,
              labels: ['{issue_label}'],
              body: [
                'The daily ZMK main-HEAD compat matrix failed.',
                '',
                `Run: ${{runUrl}}`,
                '',
                'This is likely one of:',
                '  * ZMK upstream broke zmk-keybeacon build (expected: open PR to update compatibility.yaml).',
                '  * Our own regression (expected: revert the offending PR).',
                '',
                'Close this issue once a patched release or revert ships.'
              ].join('\\n')
            }});
"""


def render(compat: dict) -> str:
    ci = compat.get("ci", {})
    schedule = ci.get("schedule", "0 6 * * *")
    matrix = ci.get("matrix", {})
    zmk_refs = matrix.get("zmk_refs", ["main", "4dd95d7", "e844eca2"])
    shields = matrix.get("shields", ["totem_left"])
    on_fail = ci.get("on_schedule_failure", {})
    issue_label = on_fail.get("issue_label", "compat-break")

    def _yaml_inline_list(items: list[str]) -> str:
        """Render as `[a, b, c]` so matrix lines read naturally."""
        return "[" + ", ".join(items) + "]"

    return HEADER.format(
        schedule=schedule,
        zmk_refs=_yaml_inline_list(zmk_refs),
        shields=_yaml_inline_list(shields),
        issue_label=issue_label,
    )


def main() -> int:
    here = Path(__file__).resolve().parent
    module_root = here.parent
    default_compat = module_root / "compatibility.yaml"
    default_workflow = module_root / ".github" / "workflows" / "zmk-main-compat.yml"

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--compat-file", type=Path, default=default_compat)
    parser.add_argument("--out", type=Path, default=default_workflow)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit 1 if rendered output differs from --out file.",
    )
    args = parser.parse_args()

    with args.compat_file.open("r", encoding="utf-8") as fh:
        compat = yaml.safe_load(fh)

    rendered = render(compat)

    if args.check:
        if not args.out.exists():
            print(f"error [regen_ci --check]: {args.out} does not exist", file=sys.stderr)
            return 1
        actual = args.out.read_text(encoding="utf-8")
        if actual == rendered:
            print(f"regen_ci --check: {args.out.name} is in sync")
            return 0
        diff = "\n".join(
            difflib.unified_diff(
                actual.splitlines(),
                rendered.splitlines(),
                fromfile=f"{args.out.name} (on disk)",
                tofile="rendered from compatibility.yaml",
                lineterm="",
            )
        )
        print(diff, file=sys.stderr)
        print(
            f"error [regen_ci --check]: {args.out} drifted from compatibility.yaml. "
            "Run `python3 scripts/regen_ci.py` and commit.",
            file=sys.stderr,
        )
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8")
    print(f"regen_ci: wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
