#!/usr/bin/env python3
"""Adds any keys from .env.example that are missing from .env.
Never overwrites existing values."""

import os, re, sys, shutil

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
example = os.path.join(root, ".env.example")
env = os.path.join(root, ".env")

if not os.path.exists(example):
    print(f"Error: {example} not found")
    sys.exit(1)

if not os.path.exists(env):
    shutil.copy(example, env)
    print("Created .env from .env.example")
    sys.exit(0)

# Find all keys already in .env
with open(env) as f:
    existing = set(re.findall(r"^([A-Z_][A-Z0-9_]*)\s*=", f.read(), re.MULTILINE))

# Parse .env.example into blocks (handles multiline quoted values)
blocks = []
with open(example) as f:
    lines = f.readlines()

i = 0
while i < len(lines):
    line = lines[i]
    match = re.match(r"^([A-Z_][A-Z0-9_]*)\s*=(.*)$", line)
    if match:
        key = match.group(1)
        value = match.group(2)
        block = line
        # Multiline: value starts with " but doesn't end with "
        if value.startswith('"') and not (value.endswith('"') and len(value) > 1):
            i += 1
            while i < len(lines):
                block += lines[i]
                if lines[i].rstrip("\n").endswith('"'):
                    break
                i += 1
        blocks.append((key, block))
    i += 1

added = 0
with open(env, "a") as f:
    for key, block in blocks:
        if key not in existing:
            f.write("\n" + block.rstrip("\n") + "\n")
            print(f"Added: {key}")
            added += 1

print(".env is up to date" if added == 0 else f"{added} new key(s) added — fill in your values")
