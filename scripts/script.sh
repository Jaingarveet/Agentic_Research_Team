#!/bin/bash

# Initialize and remove the main tex file only if git repo never existed before then clone and remove main.tex
# all of this happens inside a repo called my-paper

# earlier I was checking the github token before executing the whole script so it will return a status code of 0 for successful run in this script since it just skips the whole commit! which later makes the commit_overleaf output misleading, also under the hood the bash scripts itself uses Exit masking so we can just use this script again and again.

mkdir temp_git_integration
cd temp_git_integration

git init
git remote add overleaf https://git@git.overleaf.com/<YOUR-PROJECT-CODE>

echo "***** Midpoint in the commit ******"
    
git checkout -B main
git pull overleaf main --allow-unrelated-histories --rebase=false || true
# --allow-unrelated-histories --rebase=false for first initialization but doesn't matter since we can run this again without major overlap

touch main.tex

cp ../temp_latex_code/temp.tex main.tex
# temp.tex is garauanteed to be written since we run this in docker container where directories are usually writable permitted
echo "***** Midpoint 2 in the commit ******"

git add main.tex
git commit -m "successfully updated the repo with new content"
git push --set-upstream overleaf main

echo "***** Ending the commit ******"
