#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
