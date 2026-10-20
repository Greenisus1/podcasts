#!/usr/bin/env python3
"""Podcasts: a terminal podcast player for the Pi. Pick a show, pick an episode,
and listen. Saves your place in every episode. Episodes are .wav files in
~/podcasts/<Show Name>/. MIT, Greenisus1."""
import curses, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui

VERSION = '1.0.0'

def main():
    if '--version' in sys.argv:
        print(VERSION)
        return 0
    curses.wrapper(ui.main)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
