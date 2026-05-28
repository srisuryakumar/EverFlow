#!/bin/bash
# Build script for EverFlow - macOS
# Creates a standalone .app bundle

set -e

echo "=== EverFlow Build Script (macOS) ==="
echo ""

echo "Installing dependencies..."
pip3 install -r requirements.txt

echo ""
echo "Building app bundle..."
pyinstaller --clean EverFlow.spec

# Clean up the intermediate collection folder, keeping only the .app bundle
rm -rf dist/EverFlow

echo ""
echo "=== Build Complete ==="
echo "App location: dist/EverFlow.app"
echo ""
echo "To install:"
echo "  cp -r dist/EverFlow.app /Applications/"
echo ""
echo "To run directly:"
echo "  open dist/EverFlow.app"