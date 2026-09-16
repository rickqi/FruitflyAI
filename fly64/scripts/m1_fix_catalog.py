"""M1.1-1: fix over-escaped JSON in fix_catalog.json line 339 (fix_template)."""
import json

path = "skills/fix_catalog.json"
raw = open(path, encoding="utf-8").read()
lines = raw.splitlines(keepends=True)

# Intended template text (as EVO recorded it)
intended = ("# Fix: Add stuck_no_progress help trigger (L2a) after dialogue L2 block\n"
            "# File: fly64/fly64/main.py\n"
            '# Find the L2 block ending with "{\\"help_reason\\": None}" after dialogue_help_sent\n'
            "# Insert L2a block as shown in commit df1d5e94\n")
new_line = json.dumps("  \"fix_template\": " + intended)  # placeholder to build below
proper = "  \"fix_template\": " + json.dumps(intended) + ",\n"
lines[338] = proper  # line 339, 0-indexed 338
open(path, "w", encoding="utf-8").write("".join(lines))

json.load(open(path))
print("fix_catalog.json now VALID JSON; line 339 rewritten with correct escaping")
