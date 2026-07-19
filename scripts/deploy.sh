#!/usr/bin/env bash
# Assemble the research.trelis.com tree and deploy:
#   /                          -> site-root/ (index of live sites)
#   /llm-valuation-forecasts/  -> site/ (this project)
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf dist
mkdir -p dist/llm-valuation-forecasts
cp site-root/index.html dist/
cp site/* dist/llm-valuation-forecasts/
npx wrangler pages deploy dist --project-name trelis-research --branch main
