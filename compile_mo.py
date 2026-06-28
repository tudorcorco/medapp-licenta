import os, re, struct

PO_FILE = os.path.join('locale', 'en', 'LC_MESSAGES', 'django.po')
MO_FILE = os.path.join('locale', 'en', 'LC_MESSAGES', 'django.mo')

FALLBACK_HEADER = (
    "Content-Type: text/plain; charset=UTF-8\n"
    "Content-Transfer-Encoding: 8bit\n"
    "Language: en\n"
    "Plural-Forms: nplurals=2; plural=(n != 1);\n"
)

def extract_quoted(line):
    s = line.find('"')
    e = line.rfind('"')
    return '' if s == -1 or s == e else line[s+1:e]

def unescape(s):
    return s.replace('\\n','\n').replace('\\t','\t').replace('\\"','"').replace('\\\\','\\')

def parse_po(path):
    entries = {}
    msgid = msgstr = mode = None

    def flush():
        nonlocal msgid, msgstr, mode
        if msgid is not None and msgstr is not None:
            key = unescape(msgid)
            if key not in entries:
                entries[key] = unescape(msgstr)
        msgid = msgstr = mode = None

    with open(path, encoding='utf-8', errors='replace') as f:
        for raw in f:
            line = raw.rstrip('\r\n').lstrip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('msgid '):
                flush(); mode = 'id'; msgid = extract_quoted(line); msgstr = None
            elif line.startswith('msgstr '):
                mode = 'str'; msgstr = extract_quoted(line)
            elif line.startswith('"') and line.endswith('"'):
                c = extract_quoted(line)
                if mode == 'id':   msgid  = (msgid  or '') + c
                if mode == 'str':  msgstr = (msgstr or '') + c

    flush()
    return entries

def compile_mo(entries, output_path):
    header = entries.pop('', None) or FALLBACK_HEADER
    if 'charset' not in header.lower():
        header = FALLBACK_HEADER
    else:
        header = re.sub(r'charset\s*=\s*\S+', 'charset=UTF-8', header, flags=re.IGNORECASE)

    normal = sorted([(k.encode('utf-8'), v.encode('utf-8')) for k,v in entries.items()], key=lambda x: x[0])
    all_e  = [(b'', header.encode('utf-8'))] + normal
    N      = len(all_e)

    orig_off  = 28
    trans_off = 28 + N * 8
    str_start = 28 + N * 16

    orig_data, orig_tbl  = b'', []
    for o, _ in all_e:
        orig_tbl.append((len(o), str_start + len(orig_data)))
        orig_data += o + b'\x00'

    trans_data, trans_tbl = b'', []
    t_base = str_start + len(orig_data)
    for _, t in all_e:
        trans_tbl.append((len(t), t_base + len(trans_data)))
        trans_data += t + b'\x00'

    mo = struct.pack('<IIIIIII', 0x950412de, 0, N, orig_off, trans_off, 0, 0)
    for l, o in orig_tbl:  mo += struct.pack('<II', l, o)
    for l, o in trans_tbl: mo += struct.pack('<II', l, o)
    mo += orig_data + trans_data

    with open(output_path, 'wb') as f:
        f.write(mo)
    return N

entries = parse_po(PO_FILE)
n = compile_mo(entries, MO_FILE)
print(f'OK: {n} intrari compilate -> {MO_FILE}')