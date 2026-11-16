#!/usr/bin/env python
import re

with open('D:\\PROJECTS\\ga-generator\\services\\catalog_importer.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix line 308 - remove the extra )re.I)
old = 'name = re.sub(HOURS_RE, "", name)re.I).strip(" .:-–—")'
new = 'name = re.sub(HOURS_RE, "", name).strip(" .:-–—")'

if old in content:
    content = content.replace(old, new)
    with open('D:\\PROJECTS\\ga-generator\\services\\catalog_importer.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed catalog_importer.py line 308")
else:
    print("Old string not found, showing context...")
    # Find similar patterns
    import re as re_mod
    matches = re_mod.finditer(r're\.sub\(HOURS_RE, """, name.*?strip', content)
    for m in matches:
        print(f"  Found: {m.group()[:60]}")