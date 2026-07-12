# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This repository contains no application code. It exists solely to configure the Claude Code
environment (`.claude/`) for sessions run against this repo, in particular for use with the
HyperFrames rendering workflow.

## Structure

- `.claude/settings.json` — registers a `SessionStart` hook that runs `.claude/hooks/session-start.sh`.
- `.claude/hooks/session-start.sh` — installs `ffmpeg`/`ffprobe` via `apt-get` if they are not already
  present. It only runs when `CLAUDE_CODE_REMOTE=true` (i.e. Claude Code on the web / remote
  sessions); it is a no-op locally. ffmpeg is required for hyperframes render.

## Working in this repo

- There is no build, lint, or test tooling — changes here are almost always edits to
  `.claude/settings.json` or `.claude/hooks/session-start.sh`.
- When editing `session-start.sh`, verify it with `bash -n .claude/hooks/session-start.sh` and keep
  it idempotent (check `command -v` before installing) since it runs on every session start.
