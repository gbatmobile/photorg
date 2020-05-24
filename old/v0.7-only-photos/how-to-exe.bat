echo "Por enquanto cxfreeze nao suporta espacos nos nomes de pastas. Usando \tmp"

set PWD=%cd%

mkdir c:\tmp\photorg
copy photorg.py c:\tmp\photorg

cd C:\tools\Python36-64\Scripts

mkdir "%PWD%\exe"
python cxfreeze  c:\tmp\photorg\photorg.py --target-dir "%PWD%\exe"
cd "%PWD%\exe"