@echo off
rem Starts OpenAmika like Start_OpenAmika.bat, with her desktop pet window instead of the web page in the browser:
rem only her, transparent and always on top (launch.py --pet, pet.py). The window needs pywebview, once:
rem     envs\brain\Scripts\python.exe -m pip install -r brain\requirements-pet.txt
rem Without it the launcher says so and opens the page in the browser as usual.
call "%~dp0Start_OpenAmika.bat" --pet %*
