#!/bin/bash

# Initialize and remove the main tex file only if git repo never existed before then clone and remove main.tex
# all of this happens inside a repo called my-paper


echo "*****Starting the commit******"

if ! [[ -d .git ]]; then
  git init
  git clone https://git@git.overleaf.com/<YOUR-PROJECT-CODE>
  rm main.tex
  git remote add overleaf https://git@git.overleaf.com/<YOUR-PROJECT-CODE>
fi

echo "***** Midpoint in the commit ******"

git checkout main
git pull overleaf main --allow-unrelated-histories --rebase=false

if ! [[ -e main.tex ]]; then
    touch main.tex
fi

cp temp.tex main.tex

echo "***** Midpoint 2 in the commit ******"

git add main.tex
git commit -m "successfully updated the repo with new content"
git push --set-upstream overleaf main

rm temp.tex

echo "***** Ending the commit ******"
