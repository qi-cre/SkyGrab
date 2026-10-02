#!/usr/bin/env bash
set -euo pipefail

APP_NAME="SkyGrab"
APP_ID="io.github.kase.skygrab"
BIN_NAME="skygrab"
VERSION="0.1.0"
ARCH="x86_64"

PROJ="$(cd "$(dirname "$0")" && pwd)"
WORK="$HOME/skygrab-appimage-work"
DIST="$PROJ/dist/skygrab"
OUT_DIR="$PROJ/dist-appimage"
TOOLS="$HOME/.cache/skygrab-tools"

echo "==> 项目: $PROJ"
echo "==> 构建产物: $DIST"

if [ ! -x "$DIST/$BIN_NAME" ]; then
    echo "错误: $DIST/$BIN_NAME 不存在或不可执行"; exit 1
fi
if [ ! -f "$PROJ/skygrab.png" ]; then
    echo "错误: $PROJ/skygrab.png 不存在"; exit 1
fi

echo "==> 准备工作目录: $WORK"
rm -rf "$WORK"
mkdir -p "$WORK/AppDir/usr/bin"
mkdir -p "$WORK/AppDir/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$WORK/AppDir/usr/share/applications"
mkdir -p "$OUT_DIR"

echo "==> 拷贝 SkyGrab 到 AppDir"
cp -r "$DIST"/* "$WORK/AppDir/usr/bin/"

echo "==> 放置图标"
cp "$PROJ/skygrab.png" "$WORK/AppDir/$APP_ID.png"
cp "$PROJ/skygrab.png" "$WORK/AppDir/$APP_NAME.png"
cp "$PROJ/skygrab.png" "$WORK/AppDir/.DirIcon"
cp "$PROJ/skygrab.png" "$WORK/AppDir/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"

echo "==> 写 .desktop"
cat > "$WORK/AppDir/$APP_NAME.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=SkyGrab
GenericName=Satellite Data Downloader
Comment=Aggressive multi-source satellite data harvester
Exec=$BIN_NAME
Icon=$APP_ID
Terminal=true
Categories=Science;
Keywords=satellite;noaa;eumetsat;downloader;goes;
StartupNotify=false
DESKTOP

cp "$WORK/AppDir/$APP_NAME.desktop" \
   "$WORK/AppDir/usr/share/applications/$APP_ID.desktop"

echo "==> 生成 AppRun"
cat > "$WORK/AppDir/AppRun" <<'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/skygrab" "$@"
APPRUN
chmod +x "$WORK/AppDir/AppRun"
chmod +x "$WORK/AppDir/usr/bin/$BIN_NAME"

mkdir -p "$TOOLS"
if [ ! -x "$TOOLS/appimagetool" ]; then
    echo "==> 下载 appimagetool"
    curl -sSL -o "$TOOLS/appimagetool" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$TOOLS/appimagetool"
fi

echo "==> 打包 AppImage"
APPIMAGE_EXTRACT_AND_RUN=1 ARCH="$ARCH" "$TOOLS/appimagetool" \
    --runtime-file "$TOOLS/runtime-x86_64" \
    --no-appstream \
    "$WORK/AppDir" \
    "$OUT_DIR/$APP_NAME-$VERSION-$ARCH.AppImage"

echo
echo "==> 完成"
ls -lh "$OUT_DIR/"
