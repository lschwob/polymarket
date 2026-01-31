@echo off
REM Start script for Polymarket Trending Tracker (Windows)

echo Starting Polymarket Trending Tracker...

REM Check if virtual environment exists
if not exist "backend\venv" (
    echo Creating Python virtual environment...
    cd backend
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    cd ..
) else (
    echo Using existing virtual environment...
)

REM Start backend in a new window
echo Starting backend server...
cd backend
call venv\Scripts\activate.bat
start "Polymarket Backend" cmd /k "python run.py"
cd ..

REM Wait a bit for backend to start
timeout /t 3 /nobreak >nul

REM Check if node_modules exists
if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

REM Start frontend in a new window
echo Starting frontend server...
cd frontend
start "Polymarket Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ==========================================
echo Application started!
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Close the Backend and Frontend windows to stop the servers
echo ==========================================
echo.
pause
