pyinstaller --distpath . --onefile photorg.py
rmdir build /S /Q
del *.spec
move dist\photorg.exe .