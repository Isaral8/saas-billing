import re

with open("templates/accounts/home.html", "rb") as f:
    data = f.read()

text = data.decode("utf-8")

# Find suspicious patterns: ?? or ????? (icon placeholders), or standalone ? before a number/capital (rupee sign)
patterns = [
    (r"\?{2,}", "double-or-more ? (icon/rating placeholder)"),
    (r"\?(?=\d)", "? immediately before a digit (likely rupee sign)"),
]

seen_lines = set()
for pattern, label in patterns:
    print(f"=== {label} ===")
    for m in re.finditer(pattern, text):
        start = max(0, m.start() - 40)
        end = min(len(text), m.end() + 40)
        snippet = text[start:end].replace("\n", " ").replace("\r", "")
        key = (label, m.start())
        if key not in seen_lines:
            print(f"  at char {m.start()}: ...{snippet}...")
            seen_lines.add(key)
    print()
