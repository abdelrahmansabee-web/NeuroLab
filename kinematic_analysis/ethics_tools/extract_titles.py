import re
import sys

text = open(sys.argv[1], encoding='utf-8').read()
for m in re.finditer(r'<a[^>]*class="docsum-title"[^>]*>(.*?)</a>', text, re.S):
    title = re.sub(r'<[^>]+>', '', m.group(1))
    title = re.sub(r'\s+', ' ', title).strip()
    print(title)
