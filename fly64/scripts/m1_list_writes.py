import re
src = open("fly64/main.py").read()
lines = src.splitlines()
for i, l in enumerate(lines, 1):
    if re.search(r"\bcontrol\.\w+\s*=[^=]", l):
        print(f"{i}: {l.strip()[:90]}")
