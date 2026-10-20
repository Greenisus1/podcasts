#!/bin/bash
# pi-app-store: 1
# pi-app-store-category: apps
# pi-app-store-description: Terminal podcast player. Pick a show, pick an episode, listen - with a phone-style player (play triangle, scrubber, 10-second skips) and your place saved in every episode. Episodes are .wav files in ~/podcasts.
set -eu
cd -- "$(dirname -- "$0")"
case "${1:-}" in
 install) python3 -c 'from pathlib import Path;[compile(p.read_bytes(),str(p),"exec") for p in Path(".").glob("*.py")]' ;;
 run) shift; exec python3 podcasts.py "$@" ;;
 *) echo 'Use: bash app-store.sh install OR bash app-store.sh run';exit 1 ;;
esac
