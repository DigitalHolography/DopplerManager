@echo off
SETLOCAL
CHCP 65001

REM --- Setup ANSI Colors ---
FOR /F "tokens=1,2 delims=#" %%a IN ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') DO (
    set "ESC=%%b"
)
set "COLOR_RESET=%ESC%[0m"
set "COLOR_RED=%ESC%[91m"
set "COLOR_GREEN=%ESC%[92m"
set "COLOR_YELLOW=%ESC%[93m"

cls


REM --- Display ASCII Art Banner ---
ECHO %COLOR_YELLOW%
ECHO  ██████████                               ████                            
ECHO ░░███░░░░███                             ░░███                            
ECHO  ░███   ░░███  ██████  ████████  ████████ ░███   ██████  ████████         
ECHO  ░███    ░███ ███░░███░░███░░███░░███░░███░███  ███░░███░░███░░███        
ECHO  ░███    ░███░███ ░███ ░███ ░███ ░███ ░███░███ ░███████  ░███ ░░░         
ECHO  ░███    ███ ░███ ░███ ░███ ░███ ░███ ░███░███ ░███░░░   ░███             
ECHO  ██████████  ░░██████  ░███████  ░███████ █████░░██████  █████            
ECHO ░░░░░░░░░░    ░░░░░░   ░███░░░   ░███░░░ ░░░░░  ░░░░░░  ░░░░░             
ECHO                        ░███      ░███                                     
ECHO  ██████   ██████       █████     █████                                    
ECHO ░░██████ ██████       ░░░░░     ░░░░░                                     
ECHO  ░███░█████░███   ██████  ████████    ██████    ███████  ██████  ████████ 
ECHO  ░███░░███ ░███  ░░░░░███░░███░░███  ░░░░░███  ███░░███ ███░░███░░███░░███
ECHO  ░███ ░░░  ░███   ███████ ░███ ░███   ███████ ░███ ░███░███████  ░███ ░░░ 
ECHO  ░███      ░███  ███░░███ ░███ ░███  ███░░███ ░███ ░███░███░░░   ░███     
ECHO  █████     █████░░████████████ █████░░████████░░███████░░██████  █████    
ECHO ░░░░░     ░░░░░  ░░░░░░░░░░░░ ░░░░░  ░░░░░░░░  ░░░░░███ ░░░░░░  ░░░░░     
ECHO                                                ███ ░███                   
ECHO                                               ░░██████                    
ECHO                                                ░░░░░░                     
ECHO %COLOR_RESET%
ECHO.
ECHO. 

ECHO %COLOR_YELLOW%--- Python Version Check ---%COLOR_RESET%
FOR /F "tokens=2" %%G IN ('python --version 2^>^&1') DO set "PYTHON_VERSION=%%G"

FOR /F "tokens=1,2 delims=." %%A IN ("%PYTHON_VERSION%") DO (
    SET MAJOR_VERSION=%%A
    SET MINOR_VERSION=%%B
)

IF %MAJOR_VERSION% LSS 3 (
    ECHO %COLOR_RED%Python 3 or higher is required. Found version %PYTHON_VERSION%.%COLOR_RESET%
    GOTO :EOF
)

IF %MAJOR_VERSION% EQU 3 (
    IF %MINOR_VERSION% LSS 13 (
        ECHO %COLOR_RED%Python 3.13 or higher is required. Found version %PYTHON_VERSION%.%COLOR_RESET%
        GOTO :EOF
    )
)

ECHO %COLOR_GREEN%Python version check passed (%PYTHON_VERSION%).%COLOR_RESET%
ECHO.

REM --- Environment Setup and Application Execution ---
ECHO %COLOR_YELLOW%Creating virtual environment...%COLOR_RESET%
python -m venv venv
IF %ERRORLEVEL% NEQ 0 (
    ECHO %COLOR_RED%Failed to create virtual environment.%COLOR_RESET%
    GOTO :EOF
)

ECHO %COLOR_GREEN%Virtual environment created successfully.%COLOR_RESET%
ECHO.

ECHO %COLOR_YELLOW%Activating virtual environment...%COLOR_RESET%
CALL venv\Scripts\activate
IF %ERRORLEVEL% NEQ 0 (
    ECHO %COLOR_RED%Failed to activate virtual environment.%COLOR_RESET%
    GOTO :EOF
)

ECHO %COLOR_GREEN%Virtual environment activated.%COLOR_RESET%
ECHO.

ECHO %COLOR_YELLOW%Installing dependencies from requirements.txt...%COLOR_RESET%
pip install -r requirements.txt
IF %ERRORLEVEL% NEQ 0 (
    ECHO %COLOR_RED%Failed to install dependencies.%COLOR_RESET%
    GOTO :EOF
)

ECHO %COLOR_GREEN%Dependencies installed successfully.%COLOR_RESET%
ECHO.

ECHO %COLOR_YELLOW%Running the Streamlit application... (Press Ctrl+C to stop)%COLOR_RESET%
streamlit run app.py

ENDLOCAL