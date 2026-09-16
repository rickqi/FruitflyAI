import re, pathlib
p = pathlib.Path("skills/evolution_skill.py")
s = p.read_text()
s2, n = re.subn(r'^SKILL_VERSION = "3\.1\.0"$', 'SKILL_VERSION = "3.1.1"', s, flags=re.M)
assert n == 1, f"substitutions: {n}"
p.write_text(s2)
print("SKILL_VERSION -> 3.1.1")
