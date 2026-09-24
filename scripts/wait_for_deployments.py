import requests
import time
import sys

TARGET_COMMIT = "274eeaa"

print(f"Waiting for Render and Vercel to deploy commit {TARGET_COMMIT}...")

for attempt in range(120):
    time.sleep(5)
    
    # 1. Check Render
    render_ready = False
    try:
        r = requests.get("https://satyascan-backend.onrender.com/health", timeout=10)
        if r.status_code == 200:
            commit = r.json().get("commit")
            print(f"[{attempt+1}] Render commit: {commit}")
            if commit == TARGET_COMMIT:
                render_ready = True
    except Exception as e:
        print(f"[{attempt+1}] Render error: {e}")

    # 2. Check Vercel
    vercel_ready = False
    try:
        vr = requests.get("https://satya-scan-phi.vercel.app", headers={"Cache-Control": "no-cache"}, timeout=10)
        # Check if new chunk contains satyascan_auth_token
        html = vr.text
        # extract scripts
        import re
        script_srcs = re.findall(r'src="(/_next/static/immutable/chunks/[^"]+)"', html)
        for s in script_srcs:
            cr = requests.get(f"https://satya-scan-phi.vercel.app{s}", timeout=10)
            if "satyascan_auth_token" in cr.text:
                vercel_ready = True
                print(f"[{attempt+1}] Vercel has new chunk: {s}")
                break
    except Exception as e:
        print(f"[{attempt+1}] Vercel error: {e}")

    print(f"[{attempt+1}] Status -> Render: {'READY' if render_ready else 'BUILDING'}, Vercel: {'READY' if vercel_ready else 'BUILDING'}")

    if render_ready and vercel_ready:
        print("\n>>> BOTH RENDER AND VERCEL ARE FULLY DEPLOYED WITH TARGET COMMIT! <<<")
        sys.exit(0)

print("Timed out waiting for deployments.")
sys.exit(1)
