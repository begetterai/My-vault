#!/usr/bin/env python3
"""Собирает все ТТК-карточки из spec_*.json, сверяет состав с оригиналом (ttk_source.json),
генерит xlsx. Загрузку делает отдельно (--upload)."""
import os, sys, json, glob, re
sys.path.insert(0,'/home/user/My-vault/scripts')
from ttk_card import build_card

SP="/tmp/claude-0/-home-user-My-vault/606dd1b1-a624-5ef2-a06e-c6a894e680ba/scratchpad"
src=json.load(open(f"{SP}/ttk_source.json"))

def num(x):
    m=re.findall(r'-?\d+[.,]?\d*', str(x).replace(' ',''))
    return float(m[0].replace(',','.')) if m else None

def verify(spec):
    """Сверяем имена+нетто-веса карточки с таблицей оригинала."""
    key=spec['key']; issues=[]
    rows=src[key]['tables'][0][1:]  # без заголовка
    # оригинал: [№, Наименование, Брутто, Нетто]
    orig={}
    for r in rows:
        if len(r)>=4 and r[1].strip():
            orig[r[1].strip()]=num(r[3])
    for ing in spec['ingredients']:
        nm=ing['name'].strip(); w=num(ing['weight'])
        if nm not in orig:
            issues.append(f"[{key}] имя не совпало с оригиналом: «{nm}»")
        elif orig[nm]!=w:
            issues.append(f"[{key}] вес «{nm}»: карточка {w} ≠ оригинал {orig[nm]}")
    return issues

def main():
    specs=[]
    for f in sorted(glob.glob(f"{SP}/spec_*.json")):
        specs+=json.load(open(f))
    print(f"Всего карточек: {len(specs)}")
    all_issues=[]
    built=[]
    for spec in specs:
        iss=verify(spec); all_issues+=iss
        path=f"{SP}/{spec['filename']}"
        build_card(spec, path); built.append(path)
    print(f"Собрано xlsx: {len(built)}")
    if all_issues:
        print("\n⚠️  РАСХОЖДЕНИЯ СОСТАВА С ОРИГИНАЛОМ:")
        for i in all_issues: print("  -", i)
    else:
        print("✅ Состав всех карточек совпадает с оригиналом (имена+нетто).")
    json.dump([s['filename'] for s in specs], open(f"{SP}/_built_list.json","w"), ensure_ascii=False)
    if '--upload' in sys.argv:
        from ttk_upload import upload
        print("\nЗагрузка в Drive:")
        for p in built:
            r=upload(p); print("  ",r[0], r[2])

if __name__=='__main__':
    main()
