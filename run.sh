#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/pipeline"
STAMP=$(date +%Y-%m-%d)
python3 build.py --validate
python3 build.py --out "../out/$STAMP" --name "patterns-kn-$STAMP"
echo "Rendered: out/$STAMP/"
