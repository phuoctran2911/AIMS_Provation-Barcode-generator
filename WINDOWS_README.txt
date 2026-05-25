PROVATION BARCODE GENERATOR - WINDOWS
=====================================

How to run:

1) Install Python for Windows if you do not have it:
   https://www.python.org/downloads/windows/

   IMPORTANT: During Python install, check:
   [x] Add Python to PATH

2) Unzip this folder anywhere, for example Desktop.

3) Double-click:
   Start Provation Windows.bat

4) First launch may take a few minutes because it installs required packages.

5) Your browser should open:
   http://127.0.0.1:8000

6) Leave the black command window open while using the app.
   Close the window to stop the app.

AI API KEY
==========

If you want AI extraction:

1) Open the file named .env
2) Put your key like this:
   OPENAI_API_KEY=sk-yourkeyhere
3) Save the file
4) Restart the app

If you do not see .env, enable hidden files in Windows Explorer:
View -> Show -> Hidden items

Without API key, Excel/CSV/PDF/OCR extraction and barcode printing still work, but photo extraction is less accurate.

TESSERACT OCR OPTIONAL
======================

For local image OCR, Windows also needs Tesseract installed separately.
However, AI extraction can still read photos directly if you provide an OpenAI API key.

If you want local OCR, install Tesseract for Windows and ensure it is added to PATH.

TROUBLESHOOTING
===============

If the browser says it cannot connect:
- wait 10 seconds
- refresh the browser
- check the black command window for errors

If Python is not found:
- reinstall Python
- check "Add Python to PATH"
- restart the computer

If package installation fails:
- make sure you are connected to the internet
- try running the batch file again

Do not upload .env to GitHub or share it publicly. It contains your API key.
