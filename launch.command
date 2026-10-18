#!/bin/sh
cd "$(dirname "$0")" || exit 1
printf 'Open http://127.0.0.1:8765 in your browser. Keep this window open.\n'
python3 app.py
