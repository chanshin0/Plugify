#!/bin/bash
set -eu
root=$(cd "$(dirname "$0")" && pwd)
python3 "$root/test_reference.py"
