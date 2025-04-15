@echo off
IF "%1"=="start" (
    echo Starting RSSFeedGen in background...
    start /b "" pythonw "./main.py"
    echo RSSFeedGen is now running in background with process ID:
    for /f "tokens=2" %%a in ('tasklist /fi "imagename eq pythonw.exe" /fo list ^| find "PID:"') do echo %%a
) ELSE IF "%1"=="stop" (
    echo Attempting to stop RSSFeedGen...
    taskkill /f /im pythonw.exe 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo RSSFeedGen has been stopped successfully.
    ) else (
        echo No running RSSFeedGen process found.
    )
) ELSE (
    echo Usage: main.bat [start^|stop]
    echo   start - Starts RSSFeedGen in the background
    echo   stop  - Stops all background pythonw processes
)