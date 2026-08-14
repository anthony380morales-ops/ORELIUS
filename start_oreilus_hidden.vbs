' O.R.E.I.L.U.S. Hidden Startup Script
' Runs the backend server completely hidden in the background
' No console window will appear

Set WshShell = CreateObject("WScript.Shell")

' Change to backend directory and run uvicorn
' 0 = Hidden window, False = Don't wait for completion
WshShell.Run "cmd /c cd /d C:\Users\Victoria\oreilus\backend && venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000", 0, False

' Log the startup
Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objFile = objFSO.OpenTextFile("C:\Users\Victoria\oreilus\oreilus_startup.log", 8, True)
objFile.WriteLine(Now & " - O.R.E.I.L.U.S. backend started in background mode")
objFile.Close
