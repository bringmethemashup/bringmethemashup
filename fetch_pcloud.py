import requests
import json
import time
import os
import re

USERNAME = os.environ.get("PCLOUD_USERNAME")
PASSWORD = os.environ.get("PCLOUD_PASSWORD")

def should_skip(fname):
    fl = fname.lower()
    base = re.sub(r'\.(mp3|flac)$', '', fl)
    if 'acapella' in base and base.strip() != 'acapella mashup':
        return True
    if 'instrumental' in base:
        return True
    if 'draft' in base:
        return True
    if 'concept' in base:
        return True
    return False

def rank(fname):
    fl = fname.lower()
    score = 0
    if 'mashup mixed' in fl: score += 100
    elif 'mixed' in fl: score += 80
    if 'retimed' in fl: score += 10
    if 'version 2' in fl or 'v2' in fl: score += 5
    if 'reversed' in fl: score -= 50
    if 'official' in fl: score += 3
    return score

def simplify(name):
    n = name.lower()
    n = re.sub(r'\.(mp3|flac)$', '', n)
    for s in [' mashup mixed', ' mixed', ' mashup', ' (retimed)', ' retimed',
              ' (reversed)', ' reversed', ' (fixed)', ' version 2', ' v2',
              ' 1', ' 2', ' 3', '(official)', '(single version)', '(album version)',
              ' updated', ' extended mixed', ' extended']:
        n = n.replace(s, '')
    return re.sub(r'\s+', ' ', n).strip()

def strip_number(fname):
    return re.sub(r'^\d+\s*-\s*', '', fname)

print("Logging in to pCloud...")
auth_res = requests.get("https://api.pcloud.com/userinfo", params={
    "getauth": 1, "logout": 1,
    "username": USERNAME, "password": PASSWORD
})
auth_data = auth_res.json()

if "auth" not in auth_data:
    print("Login failed:", auth_data)
    exit(1)

auth_token = auth_data["auth"]
print("Logged in!")

print("Finding My Mashups folder...")
ls_res = requests.get("https://api.pcloud.com/listfolder", params={
    "auth": auth_token, "path": "/My Mashups", "recursive": 0
})
ls_data = ls_res.json()

if "metadata" not in ls_data:
    print("Could not find folder:", ls_data)
    exit(1)

root_folder = ls_data["metadata"]

year_folders = {'Mashups 2011','Mashups 2012','Mashups 2013','Mashups 2014',
                'Mashups 2015','Mashups 2016','Mashups 2017','Mashups 2018',
                'Mashups 2019','Mashups 2020','Mashups 2021','Mashups 2022',
                'Mashups 2023','Mashups 2024','Mashups 2025','Mashups 2026',
                'Mashups 2027','Mashups 2028'}

album_folders = {'Mash The Fatale Up', 'Mash The Fatale Up 2',
                 'K-12 Mashup Album', '1989-Night Visions Mashup Album',
                 'Mashing Pulses'}

def get_files_recursive(folder_id, folder_name, depth=0):
    files = []
    res = requests.get("https://api.pcloud.com/listfolder", params={
        "auth": auth_token, "folderid": folder_id, "recursive": 0
    })
    data = res.json()
    if "metadata" not in data:
        return files
    contents = data["metadata"].get("contents", [])
    for item in contents:
        if item.get("isfolder"):
            print(f"{'  '*depth}📁 {item['name']}")
            sub = get_files_recursive(item["folderid"], item["name"], depth+1)
            files.extend(sub)
        else:
            name = item["name"]
            if name.lower().endswith(".mp3") or name.lower().endswith(".flac"):
                year = re.search(r'(\d{4})', folder_name)
                year = year.group(1) if year else '0000'
                if '2018' in folder_name:
                    name_display = strip_number(name)
                else:
                    name_display = name
                files.append({
                    "fileid": item["fileid"],
                    "name": name_display,
                    "folder": folder_name,
                    "year": year
                })
    time.sleep(0.1)
    return files

print("Scanning all folders...")
all_files = get_files_recursive(root_folder["folderid"], "My Mashups")
print(f"Found {len(all_files)} files")

# Filter and deduplicate
from collections import defaultdict

def process_files(files):
    cleaned = [f for f in files if not should_skip(f["name"])]
    groups = defaultdict(list)
    for f in cleaned:
        s = simplify(f["name"])
        groups[s].append(f)

    result = []
    for s, variants in groups.items():
        best = sorted(variants, key=lambda x: rank(x["name"]), reverse=True)[0]
        display = re.sub(r'\.(mp3|flac)$', '', best["name"])
        result.append({
            "display": display,
            "folder": best["folder"],
            "file": best["name"],
            "year": best["year"]
        })
    return result

# Group by folder, process each
folder_files = defaultdict(list)
for f in all_files:
    folder_files[f["folder"]].append(f)

final = []
for folder, files in folder_files.items():
    processed = process_files(files)
    final.extend(processed)

# Handle cross-year dupes - keep most recent
name_groups = defaultdict(list)
for f in final:
    name_groups[f["display"].lower()].append(f)

deduped = []
for name, entries in name_groups.items():
    if len(entries) == 1:
        deduped.append(entries[0])
        continue
    year_entries = [e for e in entries if e["folder"] in year_folders]
    album_entries = [e for e in entries if e["folder"] in album_folders]
    if year_entries:
        best = sorted(year_entries, key=lambda x: x["year"], reverse=True)[0]
        deduped.append(best)
        for e in album_entries:
            e = dict(e)
            e["display"] = f"{e['display']} [{e['folder']}]"
            deduped.append(e)
    else:
        for e in entries:
            e = dict(e)
            if len(entries) > 1:
                e["display"] = f"{e['display']} [{e['folder']}]"
            deduped.append(e)

deduped.sort(key=lambda x: (x["year"], x["display"].lower()))

print(f"Final track count: {len(deduped)}")

# Write pcloud_tracks.js
lines = ['const PCLOUD_TRACKS = [']
for t in deduped:
    display = t["display"].replace("'", "\\'").replace('"', '\\"')
    folder = t["folder"].replace("'", "\\'")
    fname = t["file"].replace("'", "\\'")
    year = t["year"]
    lines.append(f"  {{ display: '{display}', folder: '{folder}', file: '{fname}', year: '{year}' }},")
lines.append('];')

with open("pcloud_tracks.js", "w") as f:
    f.write("\n".join(lines))

print("✅ Saved pcloud_tracks.js")
