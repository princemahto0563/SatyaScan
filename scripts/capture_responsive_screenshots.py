import subprocess
import os
import shutil

CONV_ID = "ec9eb643-9d7d-406a-9d38-c33537a040d6"
SCREENSHOT_DIR = f"/Users/princemahto/.gemini/antigravity-ide/brain/{CONV_ID}/screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
USER_DATA_DIR = "/tmp/chrome_satya_headless_profile"
if os.path.exists(USER_DATA_DIR):
    shutil.rmtree(USER_DATA_DIR, ignore_errors=True)

resolutions = [
    ("mobile_375x812", 375, 812),
    ("mobile_390x844", 390, 844),
    ("mobile_430x932", 430, 932),
    ("tablet_768x1024", 768, 1024),
    ("laptop_1280x800", 1280, 800),
    ("desktop_1440x900", 1440, 900),
]

common_flags = [
    CHROME,
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    f"--user-data-dir={USER_DATA_DIR}",
    "--hide-scrollbars",
    "--virtual-time-budget=2000"
]

# 1. Dark Mode Screenshots
print("--- Capturing Dark Mode Responsive Screenshots ---")
for name, w, h in resolutions:
    out_file = os.path.join(SCREENSHOT_DIR, f"{name}_dark.png")
    cmd = common_flags + [
        "--force-prefers-color-scheme=dark",
        f"--window-size={w},{h}",
        f"--screenshot={out_file}",
        "http://localhost:3000"
    ]
    print(f"Capturing {name}_dark ({w}x{h})...")
    subprocess.run(cmd, check=True)
    if os.path.exists(out_file):
        sz = os.path.getsize(out_file)
        print(f"  -> Saved {out_file} ({sz} bytes)")

# 2. Light Mode Screenshots
print("\n--- Capturing Light Mode Responsive Screenshots ---")
for name, w, h in resolutions:
    out_file = os.path.join(SCREENSHOT_DIR, f"{name}_light.png")
    cmd = common_flags + [
        "--force-prefers-color-scheme=light",
        f"--window-size={w},{h}",
        f"--screenshot={out_file}",
        "http://localhost:3000"
    ]
    print(f"Capturing {name}_light ({w}x{h})...")
    subprocess.run(cmd, check=True)
    if os.path.exists(out_file):
        sz = os.path.getsize(out_file)
        print(f"  -> Saved {out_file} ({sz} bytes)")

print("\nAll responsive screenshots captured successfully!")
