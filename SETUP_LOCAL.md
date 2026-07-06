# 🛠️ Local Development Setup Guide

**Complete step-by-step guide to set up the project locally.**

---

## Prerequisites

- Windows 10/11 or Mac/Linux
- Python 3.9+ ([Download](https://www.python.org/))
- PostgreSQL 12+ ([Download](https://www.postgresql.org/))
- Redis ([Download](https://redis.io/))
- Git ([Download](https://git-scm.com/))
- VS Code ([Download](https://code.visualstudio.com/))

---

## Step 1: Clone the Repository

```powershell
# Navigate to your projects folder
cd C:\Users\YourUsername\Desktop

# Clone the repo
git clone <your-repo-url>
cd saas-billing
```

---

## Step 2: Create Python Virtual Environment

```powershell
# Create venv
python -m venv venv

# Activate venv (Windows)
venv\Scripts\activate

# You should see: (venv) PS C:\...>
```

---

## Step 3: Install Dependencies

```powershell
# Upgrade pip
pip install --upgrade pip

# Install all packages
pip install -r requirements.txt
```

**Expected Output:**