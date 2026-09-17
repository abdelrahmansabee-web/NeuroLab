@echo off
REM OpenSim Viewer — build model + run IK via opensim-cmd, then visualize
set VENV="%~dp0venv\Scripts\python.exe"
set OPENSIMCMD="D:\Thesis app\participants\mediapipe\OpenSim 4.5\bin\opensim-cmd.exe"
set DESK="%USERPROFILE%\Desktop"
set OUTPUTS="%~dp0outputs"

echo [1/2] Building model and running IK...
%VENV% "%~dp0opensim_pipeline.py" %1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Pipeline failed
    pause
    exit /b 1
)

echo [2/2] Launching OpenSim visualizer...
start "OpenSim Visualizer" %OPENSIMCMD% viz model %DESK%\pose.osim %DESK%\pose.mot

echo Done! Close the visualizer window when done.
