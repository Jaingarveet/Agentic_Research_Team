#!/bin/bash
set -e  # Exit immediately if any command fails

# 1. Dynamically resolve the absolute path to your project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

SOURCE_TEX="$PROJECT_ROOT/temp_latex_code/temp.tex"

# 2. Check that source tex file actually exists before proceeding
if [ ! -f "$SOURCE_TEX" ]; then
    echo "Error: Source file $SOURCE_TEX does not exist!"
    exit 1
fi

# 3. Create a isolated temp directory and auto-delete it on exit
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

cd "$TEMP_DIR"

echo "***** Initializing isolated sync repo *****"
git init

# Add your project code here 

git remote add overleaf https://git@git.overleaf.com/<your project code goes here>
git checkout -B main

# Pull existing Overleaf files into temp folder
git pull overleaf main --allow-unrelated-histories --rebase=false || true

# Copy temp.tex over main.tex in the isolated temp folder
cp "$SOURCE_TEX" main.tex

echo "***** Staging and committing main.tex *****"
git add main.tex
git commit -m "successfully updated the repo with new content"
git push --set-upstream overleaf main

echo "***** Ending the commit *****"
