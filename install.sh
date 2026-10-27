#!/usr/bin/env bash
# Install these skills for any Agent Skills-compatible AI tool on this machine.
#
#   ./install.sh                 install every skill in skills/
#   ./install.sh <name> [<name>] install only those
#   ./install.sh --list          show what would happen, change nothing
#   ./install.sh --uninstall     remove links that point into this repo
#
# A SKILL.md is plain Markdown with YAML frontmatter — no tool-specific syntax.
# This script does not copy it anywhere: it symlinks, so every tool reads the
# same file and `git status` in this repo stays truthful.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/skills"

# Where skills are read from, most neutral first.
#   ~/.agents/skills  the harness-neutral convention: Codex, Cursor, Gemini,
#                     opencode and anything else that reads Agent Skills
#   ~/.claude/skills  Claude Code
NEUTRAL_DIR="$HOME/.agents/skills"
CLAUDE_DIR="$HOME/.claude/skills"

MODE=install
DRY=0
TARGETS=()
for arg in "$@"; do
  case "$arg" in
    --list|-n|--dry-run) DRY=1 ;;
    --uninstall|-u)      MODE=uninstall ;;
    -h|--help)           sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*)                  echo "unknown option: $arg" >&2; exit 2 ;;
    *)                   TARGETS+=("$arg") ;;
  esac
done

if [ ${#TARGETS[@]} -eq 0 ]; then
  for d in "$SRC"/*/; do [ -d "$d" ] && TARGETS+=("$(basename "$d")"); done
fi

claude_has_plugin() {
  command -v claude >/dev/null 2>&1 || return 1
  claude plugin list 2>/dev/null | grep -qF -- "$1@"
}

# link <source> <destination>; never touches anything that is not our symlink
link() {
  local src=$1 dst=$2
  if [ -L "$dst" ]; then
    local cur; cur="$(readlink "$dst")"
    case "$cur" in
      "$src"|*"$(basename "$REPO")/skills/$(basename "$src")")
        echo "    = already linked" ; return 0 ;;
    esac
    echo "    ! $dst is a symlink to something else ($cur) — left alone" >&2
    return 1
  fi
  if [ -e "$dst" ]; then
    echo "    ! $dst exists and is not a symlink — left alone" >&2
    return 1
  fi
  [ "$DRY" = 1 ] && { echo "    + would link $dst"; return 0; }
  mkdir -p "$(dirname "$dst")"
  ln -s "$src" "$dst"
  echo "    + linked $dst"
}

unlink_ours() {
  local dst=$1
  [ -L "$dst" ] || return 0
  case "$(readlink "$dst")" in
    "$REPO"/*|*"$(basename "$REPO")/skills/"*)
      [ "$DRY" = 1 ] && { echo "    - would remove $dst"; return 0; }
      rm "$dst"; echo "    - removed $dst" ;;
    *) echo "    ! $dst points outside this repo — left alone" >&2 ;;
  esac
}

echo "repo: $REPO"
echo "mode: $MODE$([ "$DRY" = 1 ] && echo " (dry run — changes nothing)")"
echo

for name in "${TARGETS[@]}"; do
  src="$SRC/$name"
  if [ ! -f "$src/SKILL.md" ]; then
    echo "$name: no skills/$name/SKILL.md — skipped" >&2
    continue
  fi
  echo "$name"

  if [ "$MODE" = uninstall ]; then
    unlink_ours "$NEUTRAL_DIR/$name"
    unlink_ours "$CLAUDE_DIR/$name"
    continue
  fi

  # 1. the neutral home every other tool reads
  link "$src" "$NEUTRAL_DIR/$name"

  # 2. Claude Code — skip when the plugin build of the same skill is installed,
  #    since the same skill name registered twice gets loaded twice
  if claude_has_plugin "$name"; then
    echo "    = Claude Code: skipped, plugin '$name' is installed"
    echo "      (use one or the other: claude plugin uninstall $name, then re-run)"
  else
    link "$src" "$CLAUDE_DIR/$name"
  fi
done

cat <<EOF

Tools that read a directory of skills pick these up on their own:
  ~/.agents/skills   Codex, Cursor, Gemini CLI, opencode, and others
  ~/.claude/skills   Claude Code

A tool that reads only one instructions file (AGENTS.md, GEMINI.md, .cursorrules)
needs a pointer instead of a link. Add a line like this to it by hand, so you
stay in control of that file:

  When a task matches a skill under ~/.agents/skills/, read that SKILL.md first
  and follow it.

Skills are instructions, not programs: nothing here runs until an agent decides
to follow a SKILL.md. The Python under skills/*/scripts/ runs only when the
skill tells the agent to call it.
EOF
