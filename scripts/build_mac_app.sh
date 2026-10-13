#!/bin/bash
# Builds Internbot.app and installs it in ~/Applications (Spotlight and the Dock can find it).
# Re-run after moving this project folder. Quitting = closing the window; the server stops itself.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HOME/Applications/Internbot.app"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Internbot</string>
  <key>CFBundleDisplayName</key><string>Internbot</string>
  <key>CFBundleIdentifier</key><string>local.internbot.dashboard</string>
  <key>CFBundleExecutable</key><string>internbot</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSUIElement</key><true/>
</dict></plist>
PLIST

cat > "$APP/Contents/MacOS/internbot" <<LAUNCH
#!/bin/bash
URL="http://127.0.0.1:8765"
fail() { osascript -e "display alert \"Internbot could not start\" message \"\$1\"" >/dev/null 2>&1; exit 1; }
cd "$ROOT" 2>/dev/null || fail "Cannot open $ROOT. Allow Internbot under System Settings > Privacy & Security > Files and Folders (Desktop), or move the project out of Desktop and rebuild."
mkdir -p "$ROOT/local" 2>/dev/null || fail "Cannot write to $ROOT/local."
if ! curl -s -o /dev/null "\$URL/api/ping"; then
  nohup "$PY" -m internbot.site --no-open --exit-when-closed > "$ROOT/local/site.log" 2>&1 &
  for _ in \$(seq 1 40); do curl -s -o /dev/null "\$URL/api/ping" && break; sleep 0.25; done
  curl -s -o /dev/null "\$URL/api/ping" || fail "The server did not start. Last log lines: \$(tail -3 "$ROOT/local/site.log" | tr '"' "'")"
fi
# A standalone window (no tabs or address bar) when Chrome is installed, else the default browser.
if [ -d "/Applications/Google Chrome.app" ]; then
  open -na "Google Chrome" --args --app="\$URL" --user-data-dir="$ROOT/local/chrome-profile"
else
  open "\$URL"
fi
LAUNCH
chmod +x "$APP/Contents/MacOS/internbot"
mkdir -p "$ROOT/local"

# Icon: a blue rounded square with a white "i", drawn with the standard library only.
"$PY" - "$APP/Contents/Resources" <<'PYICON'
import struct, subprocess, sys, tempfile, zlib, os
N = 1024
def inside(x, y):
    r = 190; cx = min(max(x, r), N - r); cy = min(max(y, r), N - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r
def white(x, y):
    stem = 450 <= x <= 574 and 430 <= y <= 780
    dot = (x - 512) ** 2 + (y - 300) ** 2 <= 75 ** 2
    return stem or dot
rows = []
for y in range(N):
    row = bytearray([0])
    for x in range(N):
        if not inside(x, y): row += b"\x00\x00\x00\x00"
        elif white(x, y): row += b"\xff\xff\xff\xff"
        else: row += bytes([47 + y * 30 // N, 111 + y * 20 // N, 237, 255])
    rows.append(bytes(row))
raw = b"".join(rows)
def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", N, N, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
d = tempfile.mkdtemp(); iconset = os.path.join(d, "icon.iconset"); os.mkdir(iconset)
base = os.path.join(d, "base.png"); open(base, "wb").write(png)
for s in (16, 32, 128, 256, 512):
    subprocess.run(["sips", "-z", str(s), str(s), base, "--out", f"{iconset}/icon_{s}x{s}.png"], capture_output=True, check=True)
    subprocess.run(["sips", "-z", str(s*2), str(s*2), base, "--out", f"{iconset}/icon_{s}x{s}@2x.png"], capture_output=True, check=True)
subprocess.run(["iconutil", "-c", "icns", iconset, "-o", os.path.join(sys.argv[1], "icon.icns")], check=True)
PYICON

codesign --force --sign - "$APP" >/dev/null 2>&1 || true
touch "$APP"
echo "Installed $APP"
