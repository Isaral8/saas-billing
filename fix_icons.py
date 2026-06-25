with open("templates/accounts/home.html", "rb") as f:
    data = f.read()

icons = ["👤", "💼", "📄", "🧾", "💳", "💬"]
marker = b'step-icon">??</div>'

pos = 0
for icon in icons:
    idx = data.find(marker, pos)
    if idx == -1:
        print("Ran out of matches early - only filled", icons.index(icon), "icons")
        break
    replacement = ("step-icon\">" + icon + "</div>").encode("utf-8")
    data = data[:idx] + replacement + data[idx+len(marker):]
    pos = idx + len(replacement)
    print(f"Placed {icon} at position {idx}")

with open("templates/accounts/home.html", "wb") as f:
    f.write(data)
print("Done")
