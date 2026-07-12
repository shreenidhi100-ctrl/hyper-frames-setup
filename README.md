# Ganita Video Pipeline

Kannada animated math explainer videos + synced SRT, generated from a
deterministic canvas renderer. See CLAUDE.md for architecture and
conventions (that file is also the brief for Claude Code sessions).

Quick start:
    pip install -r requirements.txt && playwright install chromium
    cd pipeline && python3 build.py --validate && python3 build.py

Custom Claude Code commands: /render, /new-scene, /new-chapter-plan
