"""
GEM Automation Router - Runs gem_add.py and gem_master.py from frontend
"""
import subprocess
import os
import httpx
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter(prefix="/api/gem", tags=["gem-automation"])

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# GEM portal URLs to detect
GEM_FORM_PATTERNS = [
    "gem.gov.in",
    "mkp.gem.gov.in",
    "admin-mkp.gem.gov.in"
]

GEM_ADD_FORM_PATTERNS = [
    "/seller/product/add",
    "/seller/products/add",
    "/product/add",
    "/catalog/new",
    "catalog/new"
]

GEM_EDIT_FORM_PATTERNS = [
    "/seller/product/edit",
    "/seller/products/edit",
    "/product/edit",
    "/catalog/edit",
    "catalog/edit"
]


@router.get("/status")
async def get_gem_status():
    """Check if Chrome is running and detect GEM form status"""
    import socket
    
    chrome_connected = False
    gem_tabs = []
    form_detected = None
    form_type = None
    active_tab_url = None
    
    # Check Chrome port
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 9222))
        chrome_connected = result == 0
        sock.close()
    except:
        pass
    
    # If Chrome connected, check tabs via remote debugging API
    if chrome_connected:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get("http://127.0.0.1:9222/json")
                tabs = response.json()
                
                for tab in tabs:
                    url = tab.get("url", "")
                    title = tab.get("title", "")
                    tab_type = tab.get("type", "")
                    
                    # Only check page tabs
                    if tab_type != "page":
                        continue
                    
                    # Check if it's a GEM tab
                    is_gem = any(pattern in url for pattern in GEM_FORM_PATTERNS)
                    
                    if is_gem:
                        gem_tabs.append({
                            "url": url,
                            "title": title
                        })
                        
                        # Check for add form
                        if any(pattern in url.lower() for pattern in GEM_ADD_FORM_PATTERNS):
                            form_detected = True
                            form_type = "add"
                            active_tab_url = url
                        
                        # Check for edit form
                        elif any(pattern in url.lower() for pattern in GEM_EDIT_FORM_PATTERNS):
                            form_detected = True
                            form_type = "edit"
                            active_tab_url = url
                
        except Exception as e:
            pass
    
    # Build response message
    if not chrome_connected:
        message = "Chrome not connected on port 9222"
    elif form_detected:
        message = f"GEM {form_type.upper()} form detected"
    elif len(gem_tabs) > 0:
        message = f"GEM portal open ({len(gem_tabs)} tab(s)), but no form detected"
    else:
        message = "Chrome connected, but no GEM tabs open"
    
    return {
        "chrome_connected": chrome_connected,
        "gem_tabs": gem_tabs,
        "form_detected": form_detected,
        "form_type": form_type,
        "active_tab_url": active_tab_url,
        "message": message
    }


@router.post("/add-products")
async def run_add_products(
    filter_status: str = Query("NEW", description="Filter products by status (NEW, ACTIVE, etc)")
):
    """
    Run gem_add.py to add NEW products to GEM portal
    Returns immediately, script runs in background
    """
    # Check Chrome first
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 9222))
        if result != 0:
            raise HTTPException(
                status_code=400, 
                detail="Chrome not running. Start with: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222"
            )
        sock.close()
    except HTTPException:
        raise
    except:
        raise HTTPException(status_code=400, detail="Cannot check Chrome connection")
    
    # Clear any previous stop signal
    stop_file = os.path.join(BACKEND_DIR, ".stop_automation")
    if os.path.exists(stop_file):
        os.remove(stop_file)
    
    # Run gem_add.py in background
    script_path = os.path.join(BACKEND_DIR, "gem_add.py")
    
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="gem_add.py not found")
    
    try:
        # Run script in background using subprocess
        process = subprocess.Popen(
            ["python", script_path],
            cwd=BACKEND_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        return {
            "success": True,
            "message": f"gem_add.py started (PID: {process.pid})",
            "pid": process.pid,
            "filter": filter_status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start script: {str(e)}")


@router.post("/update-products")
async def run_update_products():
    """
    Run gem_master.py to update ACTIVE products on GEM portal
    Returns immediately, script runs in background
    """
    # Check Chrome first
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 9222))
        if result != 0:
            raise HTTPException(
                status_code=400, 
                detail="Chrome not running. Start with: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222"
            )
        sock.close()
    except HTTPException:
        raise
    except:
        raise HTTPException(status_code=400, detail="Cannot check Chrome connection")
    
    # Run gem_master.py in background
    script_path = os.path.join(BACKEND_DIR, "gem_master.py")
    
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="gem_master.py not found")
    
    try:
        process = subprocess.Popen(
            ["python", script_path],
            cwd=BACKEND_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        return {
            "success": True,
            "message": f"gem_master.py started (PID: {process.pid})",
            "pid": process.pid
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start script: {str(e)}")


@router.get("/chrome-command")
async def get_chrome_command():
    """Get the command to start Chrome with remote debugging (separate instance)"""
    import platform
    
    system = platform.system()
    
    if system == "Darwin":  # Mac
        cmd = '/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug'
    elif system == "Windows":
        # Find actual Chrome path on Windows
        chrome_paths = [
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
            os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
        ]
        chrome_path = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_path = path
                break
        
        if chrome_path:
            cmd = f'"{chrome_path}" --remote-debugging-port=9222 --user-data-dir=%TEMP%\\chrome-debug'
        else:
            cmd = '"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222 --user-data-dir=%TEMP%\\chrome-debug'
    else:  # Linux
        cmd = 'google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug'
    
    return {
        "platform": system,
        "command": cmd
    }


STOP_FILE = os.path.join(BACKEND_DIR, ".stop_automation")

@router.post("/stop-automation")
async def stop_automation():
    """Signal the running automation to stop"""
    try:
        # Create stop signal file
        with open(STOP_FILE, "w") as f:
            f.write("STOP")
        return {"success": True, "message": "Stop signal sent. Automation will stop after current product."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send stop signal: {str(e)}")


@router.post("/clear-stop")
async def clear_stop():
    """Clear the stop signal (called when starting new automation)"""
    try:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
        return {"success": True}
    except:
        pass
    return {"success": True}


@router.get("/automation-status")
async def get_automation_status():
    """Check if automation is running or stopped"""
    stop_requested = os.path.exists(STOP_FILE)
    return {
        "stop_requested": stop_requested
    }


@router.post("/launch-chrome")
async def launch_chrome():
    """Launch a NEW Chrome instance with remote debugging (doesn't close existing Chrome)"""
    import platform
    import subprocess
    import shutil
    import socket
    
    system = platform.system()
    
    # First check if debug port is already in use (Chrome with debug already running)
    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0
    
    if is_port_in_use(9222):
        return {"success": True, "message": "Debug Chrome already running on port 9222!", "platform": system}
    
    try:
        # Launch a SEPARATE Chrome instance with its own profile (won't affect existing Chrome)
        if system == "Darwin":  # Mac
            chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            debug_profile = '/tmp/chrome-debug-profile'
            
            if os.path.exists(chrome_path):
                subprocess.Popen([
                    chrome_path,
                    '--remote-debugging-port=9222',
                    f'--user-data-dir={debug_profile}'
                ], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return {"success": True, "message": "New debug Chrome launched on port 9222 (separate instance)", "platform": "Mac"}
            else:
                raise HTTPException(status_code=404, detail="Chrome not found at /Applications/Google Chrome.app")
                
        elif system == "Windows":
            # Try common Windows Chrome paths
            chrome_paths = [
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
            ]
            
            chrome_path = None
            for path in chrome_paths:
                if os.path.exists(path):
                    chrome_path = path
                    break
            
            if chrome_path:
                # Use a SEPARATE user-data-dir to run alongside existing Chrome
                debug_profile = os.path.expandvars(r'%TEMP%\chrome-debug-profile')
                
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                subprocess.Popen(
                    [chrome_path, '--remote-debugging-port=9222', f'--user-data-dir={debug_profile}'],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                    startupinfo=startupinfo,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return {"success": True, "message": "New debug Chrome launched on port 9222 (separate instance)", "platform": "Windows"}
            else:
                raise HTTPException(
                    status_code=404, 
                    detail="Chrome not found. Run manually: chrome.exe --remote-debugging-port=9222 --user-data-dir=%TEMP%\\chrome-debug"
                )
        else:  # Linux
            if shutil.which('google-chrome'):
                subprocess.Popen([
                    'google-chrome', 
                    '--remote-debugging-port=9222', 
                    '--user-data-dir=/tmp/chrome-debug-profile'
                ], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return {"success": True, "message": "New debug Chrome launched on port 9222 (separate instance)", "platform": "Linux"}
            else:
                raise HTTPException(status_code=404, detail="google-chrome not found in PATH")
    
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Chrome not found: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch Chrome: {str(e)}")
