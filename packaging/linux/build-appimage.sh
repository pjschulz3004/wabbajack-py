#!/bin/bash
# Build AppImage for wabbajack-py
# Requires: pyinstaller, appimagetool
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$PROJECT_DIR/dist/AppDir"

echo "=== Building wabbajack-py AppImage ==="

# Build frontend
cd "$PROJECT_DIR/frontend"
npm run build
cd "$PROJECT_DIR"
python build.py

# Build with PyInstaller
pyinstaller wabbajack-py.spec --noconfirm

# Create AppDir structure
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps"

cp dist/wabbajack-py "$BUILD_DIR/usr/bin/"
cp "$SCRIPT_DIR/wabbajack-py.desktop" "$BUILD_DIR/usr/share/applications/"
cp "$BUILD_DIR/usr/share/applications/wabbajack-py.desktop" "$BUILD_DIR/"

# Create AppRun
cat > "$BUILD_DIR/AppRun" << 'APPRUN'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
exec "${HERE}/usr/bin/wabbajack-py" "$@"
APPRUN
chmod +x "$BUILD_DIR/AppRun"

# Build AppImage
if command -v appimagetool &>/dev/null; then
    ARCH=x86_64 appimagetool "$BUILD_DIR" "$PROJECT_DIR/dist/wabbajack-py-x86_64.AppImage"
    echo "AppImage: dist/wabbajack-py-x86_64.AppImage"
else
    echo "appimagetool not found. AppDir ready at: $BUILD_DIR"
    echo "Install: https://github.com/AppImage/AppImageKit/releases"
fi
