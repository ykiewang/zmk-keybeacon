#!/usr/bin/env bash
# one-time-setup.sh — commands a new maintainer runs ONCE after cloning
# zmk-keybeacon (or taking over the repo). Each block is idempotent-ish;
# re-running after the first setup is safe (gh label create will error
# harmlessly on an already-existing label).
#
# This file is tracked so the setup commands live with the code rather
# than in tribal knowledge.

set -euo pipefail

# -----------------------------------------------------------------------
# 1. GitHub label for the compat matrix issue bot (used by
#    .github/workflows/zmk-main-compat.yml's file-issue-on-main-break job).
#    The label name must match compatibility.yaml:ci.on_schedule_failure.issue_label.
# -----------------------------------------------------------------------
echo "[1/1] creating GitHub label 'compat-break' …"
gh label create compat-break \
    --color d73a4a \
    --description "ZMK upstream broke zmk-keybeacon build; see compatibility matrix" \
    || echo "    (label already exists, skipping)"

echo "setup complete."
