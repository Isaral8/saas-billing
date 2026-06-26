with open("templates/accounts/settings.html", "rb") as f:
    data = f.read()
text = data.decode("utf-8")
idx = text.find("Account Prefer")
print(repr(text[idx-10:idx+10]))
