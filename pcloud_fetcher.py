import requests
import json
import time

USERNAME = "ianjurman@gmail.com"
PASSWORD = "Pcloudp@ssw0rD"

# Step 1: Login
print("Logging in to pCloud...")
auth_res = requests.get("https://api.pcloud.com/userinfo", params={
    "getauth": 1,
    "logout": 1,
    "username": USERNAME,
    "password": PASSWORD
})
auth_data = auth_res.json()

if "auth" not in auth_data:
    print("Login failed:", auth_data)
    exit()

auth_token = auth_data["auth"]
print(f"Logged in! Token: {auth_token[:10]}...")

# Step 2: Find the "My Mashups" folder
print("\nFinding My Mashups folder...")
ls_res = requests.get("https://api.pcloud.com/listfolder", params={
    "auth": auth_token,
    "path": "/My Mashups",
    "recursive": 0
})
ls_data = ls_res.json()

if "metadata" not in ls_data:
    print("Could not find folder:", ls_data)
    exit()

root_folder = ls_data["metadata"]
print(f"Found folder: {root_folder['name']} (id: {root_folder['folderid']})")

# Step 3: Recursively get all files
def get_files_recursive(folder_id, folder_name, depth=0):
    files = []
    res = requests.get("https://api.pcloud.com/listfolder", params={
        "auth": auth_token,
        "folderid": folder_id,
        "recursive": 0
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
            # Only MP3 and FLAC, skip .asd and other files
            if name.lower().endswith(".mp3") or name.lower().endswith(".flac"):
                files.append({
                    "fileid": item["fileid"],
                    "name": name,
                    "folder": folder_name,
                    "path": item.get("path", "")
                })
    time.sleep(0.1)  # be nice to the API
    return files

print("\nScanning all folders (this may take a minute)...")
all_files = get_files_recursive(root_folder["folderid"], "My Mashups")
print(f"\nFound {len(all_files)} MP3/FLAC files total")

# Step 4: Get direct download links for each file
print("\nGenerating download links...")
results = []
for i, f in enumerate(all_files):
    if i % 50 == 0:
        print(f"  Processing {i}/{len(all_files)}...")
    
    link_res = requests.get("https://api.pcloud.com/getfilelink", params={
        "auth": auth_token,
        "fileid": f["fileid"]
    })
    link_data = link_res.json()
    
    if "hosts" in link_data and "path" in link_data:
        host = link_data["hosts"][0]
        path = link_data["path"]
        direct_url = f"https://{host}{path}"
    else:
        direct_url = ""
    
    results.append({
        "name": f["name"],
        "folder": f["folder"],
        "url": direct_url
    })
    time.sleep(0.05)

print(f"\nDone! Generated {len(results)} links")

# Step 5: Output as JS file
js_lines = ["const PCLOUD_DIRECT = {"]
for r in results:
    name_key = r["name"].lower().replace('"', '\\"')
    url = r["url"]
    js_lines.append(f'  "{name_key}": "{url}",')
js_lines.append("};")

with open("pcloud_direct.js", "w") as f:
    f.write("\n".join(js_lines))

print("\n✅ Saved pcloud_direct.js - download this file from Replit!")
print("(Click the three dots next to the file in the left panel → Download)")
