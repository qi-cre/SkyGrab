# Architecture

TUI (app.py) -> call_from_thread -> DownloadEngine (engine.py)
Engine -> ThreadPoolExecutor -> os.pwrite -> .part file
Engine -> sources/eumetsat.py | sources/noaa.py
