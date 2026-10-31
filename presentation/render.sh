#!/bin/sh
# Rebuild deck.pptx and render slide previews into render/.
set -e
cd "$(dirname "$0")"
NODE_PATH=$PWD/node_modules node build.js
rm -rf render && mkdir render && cd render
/Applications/LibreOffice.app/Contents/MacOS/soffice --headless --convert-to pdf ../Bookly-pitch.pptx >/dev/null 2>&1
pdftoppm -jpeg -r 70 Bookly-pitch.pdf slide
