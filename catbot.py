#!/usr/bin/env python3
import subprocess
import sys
import time
import math
import os
import json
import socket
import pwinput
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.firefox.service import Service

# =====================================================================
# ⚙️ CONFIGURATION: EDIT YOUR CREDENTIALS HERE
# =====================================================================
print("🔐 --- Just-Dice Bot Security Portal ---")

# Kept raw—no stripping of any trailing or leading spaces
someone = input("Enter your username: ")

# Displays asterisks (*) on your terminal screen as you type
logmein = pwinput.pwinput(prompt="Enter your password: ", mask="*")

# Kept raw—no stripping of any spaces from your 2FA token
mecode = pwinput.pwinput(prompt="Enter your 2FA code or press Enter if blank: ", mask="*")
# =====================================================================

# Forced absolute storage path inside your isolated container user directory
STATE_FILE = "/home/snowy/catbot_state.json"

# ---------------------------
# STATE FILE FUNCTIONS
# ---------------------------
def load_state():
    """Loads the state file. Returns None if it doesn't exist or is invalid."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                print("🔄 Found state file. Attempting recovery...")
                return json.load(f)
        except json.JSONDecodeError:
            print("⚠️ State file was corrupted. Starting fresh.")
    return None

def save_state(state_dict):
    """Saves current global variables to the state file securely inside the container."""
    state_dict["last_seen_timestamp"] = time.time()
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state_dict, f, indent=4)
            f.flush()
    except PermissionError:
        print(f"❌ Permission Denied! Cannot write to {STATE_FILE} inside sandbox container.")
    except Exception as e:
        print(f"⚠️ Failed to save state file: {e}")

# Load existing state early to check for previous run data
saved_state = load_state()

# Setup Firefox WebDriver
options = webdriver.FirefoxOptions()
options.add_argument('--headless')  
GECKODRIVER_PATH = "/usr/bin/geckodriver"   
service = Service(GECKODRIVER_PATH)
driver = webdriver.Firefox(service=service, options=options)

# ---------------------------
# HELPERS
# ---------------------------
def f8(x):
    return float(f"{x:.8f}")

def refresh_network_whitelist():
    """Dynamically resolves new Cloudflare IPs and injects them into nftables and /etc/hosts."""
    print("🔄 [Network Sync] Resolving latest Cloudflare edge IPs...")
    try:
        # Resolve fresh live IPs from DNS inside the container
        new_jd_ip = socket.gethostbyname("just-dice.com")
        new_cf_ip = socket.gethostbyname("cloudflareinsights.com")
        
        print(f"🎯 New Just-Dice IP: {new_jd_ip}")
        print(f"🎯 New Cloudflare Insights IP: {new_cf_ip}")

        # 1. Update /etc/hosts so Selenium targets the right addresses
        hosts_cmd = f"echo '{new_jd_ip} just-dice.com\n{new_cf_ip} cloudflareinsights.com' > /etc/hosts"
        subprocess.run(["sudo", "sh", "-c", hosts_cmd], check=True)

        # 2. Flush old elements and swap in the new live IPs inside nftables
        subprocess.run(["sudo", "nft", "flush", "set", "inet", "filter", "allowed_ips"], check=True)
        subprocess.run(["sudo", "nft", "add", "element", "inet", "filter", "allowed_ips", f"{{ {new_jd_ip}, {new_cf_ip} }}"], check=True)
        print("✅ [Network Sync] Firewalls and host maps successfully synchronized!")
    except Exception as e:
        print(f"⚠️ [Network Sync Failed] Could not update dynamic rules: {e}")

# ---------------------------
# PROCESS INITIALIZATION / REFRESH FUNCTION
# ---------------------------
def initialize_bot_process(keep_old_data=False):
    """Handles browser loading, logging in, and setting up variables (either fresh or keeping old progress)."""
    global origiun, fox, bear, kitty, chance, mookie, kool, sevens, eights, fart
    global scratchPad, litterbox, mymat, matworking, mile, lastLeap, blue

    print("\n🌐 Page loading, please wait...")
    driver.get("https://just-dice.com")
    time.sleep(15)
    print("✅ Page loaded successfully!")

    try:
        popup = driver.find_element(By.CSS_SELECTOR, "a.fancybox-item.fancybox-close")
        popup.click()
    except NoSuchElementException:
        pass  

    time.sleep(2)
    driver.find_element(By.LINK_TEXT, "Account").click()
    time.sleep(3)

    print("🔑 Logging in now, please wait...")
    driver.find_element(By.ID, "myuser").clear()
    driver.find_element(By.ID, "myuser").send_keys(someone)
    driver.find_element(By.ID, "mypass").clear()
    driver.find_element(By.ID, "mypass").send_keys(logmein)
    driver.find_element(By.ID, "mycode").clear()
    driver.find_element(By.ID, "mycode").send_keys(mecode)
    driver.find_element(By.ID, "myok").click()

    print("⏳ Waiting for login to complete and dashboard to load...")
    time.sleep(15)

    # Interact with UI layout components on fresh page attachment
    # --- SAFETY BUFFER FOR BALANCE LOAD ---
    print("⏳ Waiting for dashboard metrics to resolve...")
    attempts = 0
    while attempts < 30:
        raw_val = driver.find_element(By.ID, "pct_balance").get_attribute("value")
        if raw_val and "loading" not in raw_val.lower():
            try:
                ui_balance = float(raw_val)
                break
            except ValueError:
                pass
        time.sleep(1)
        attempts += 1
    else:
        # Fallback if it takes longer than 30 seconds
        ui_balance = float(driver.find_element(By.ID, "pct_balance").get_attribute("value"))

    driver.find_element(By.ID, "b_min").click()

    # Scenario A: Watchdog-triggered runtime recovery (Do not overwrite with stale ui_balance)
    if keep_old_data:
        print("💾 [WATCHDOG RECOVERY] Page refreshed. Keeping variables intact to let loop catch true balance.")
        return

    # Scenario B: Script crash/startup recovery from local storage file
    if saved_state and (time.time() - saved_state.get("last_seen_timestamp", 0) > 55):
        time_elapsed = time.time() - saved_state["last_seen_timestamp"]
        print(f"🚨 [Startup Recovery] Bot was offline for {round(time_elapsed, 1)} seconds! Restoring previous state...")
        
        origiun = saved_state.get("origiun", ui_balance) 
        fox = saved_state["fox"]
        kitty = saved_state["kitty"]
        mookie = saved_state["mookie"]
        bear = saved_state["bear"]
        kool = (bear*10)
        sevens = (bear*6.9)
        eights = (bear*7.9)
        fart = saved_state["fart"]
        scratchPad = saved_state["scratchPad"]
        litterbox = saved_state["litterbox"] 
        
        # Fetch fresh balance from the application layout
        bocance = driver.find_element(By.ID, "pct_balance").get_attribute("value")
        # Convert to float
        viagra = float(bocance)
        if ((viagra == round((scratchPad + kitty), 8)) or (viagra == round((litterbox - kitty), 8))):
            scratchPad = viagra
            litterbox = viagra
        mile = saved_state["mile"]
        lastLeap = saved_state["lastLeap"]
        heartbeat = True
        
    # Scenario C: Clean startup initialization
    else:
        print("🚀 Fresh start. Calculating base initial variables.")
        origiun = float(ui_balance)
        fox = origiun
        yobbo = (origiun/144000)
        bear = round(yobbo, 8)
        kitty = bear
        fart = 1
        mookie = origiun
        kool = (bear*10)
        sevens = (bear*6.9)
        eights = (bear*7.9)
        scratchPad = float(fox)
        litterbox = float(fox)
        lastLeap = float(fox-bear)
        mile = ((math.floor(origiun/kool))*kool)
        heartbeat = True

# Execute basic process instantiation
initialize_bot_process(keep_old_data=False)

# Tracking clocks tailored directly for 'fox' state evaluation
LAST_FOX_VALUE = fox
LAST_FOX_CHANGE_TIMESTAMP = time.time()

# ---------------------------
# BOT LOGIC
# ---------------------------
def runCatBot():
    global fox, kitty, heartbeat, lastLeap, mookie, scratchPad, litterbox, origiun, mile, fart

    # Fetch fresh balance from the application layout
    becance = driver.find_element(By.ID, "pct_balance").get_attribute("value")

    mookie = float(becance)
    
    if ((mookie == scratchPad) or (mookie == litterbox)):
        fox = float(mookie)
        heartbeat = True
        if (fox >= (mile+(kool*fart))):
            lastLeap = float(fox-bear)
            kitty = bear
            fart = 1
            mile = ((math.floor((float(fox))/kool))*kool)
            print("[System] Upper handbrake triggered")

        if ((fox>(((math.floor(fox/kool))*kool)+sevens)) and (fox<(((math.floor(fox/kool))*kool)+eights)) and (fox>lastLeap)):
            lastLeap = float(fox)   
            kitty = kitty * 2 

        if ((fox>(((math.floor(fox/kool))*kool)+sevens)) and (fox<(((math.floor(fox/kool))*kool)+eights)) and (fox<lastLeap)):
            lastLeap = float(fox)
            fart = 0   
            kitty = kitty * 2 

        if ((fox>=(lastLeap+(kitty*10))) or (fox<=(lastLeap-(kitty*10)))):
            print("over clicking Stopping bot.")
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE) 
            heartbeat = False
            sys.exit()

        if (fox >= (origiun * 1.24)):
            print("🔄 Refreshing page, target for compound achived but preserving reseting progress variables...")
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE) 
            heartbeat = False
            try:
                driver.refresh()
                # Resolve fresh Cloudflare IPs and apply them to firewall rules dynamically
                refresh_network_whitelist()

                # Trigger a browser refresh flow while locking current progression constants
                initialize_bot_process(keep_old_data=False)
                
                # Re-zero out verification values to prevent dynamic looping loops
                LAST_FOX_VALUE = fox
                LAST_FOX_CHANGE_TIMESTAMP = time.time() 
                print("✅ Reset complete. Resuming loop...")
            except Exception as e:
                print(f"⚠️ Error during initialization: {e}. Retrying next cycle...")
                time.sleep(5) 

        if (fox >= 144000):
            print("🔄 winner winner chicken dinner...") 
            heartbeat = False
            sys.exit()

        if (heartbeat):
            netTreats = f8(fox - origiun)
            print(f"Current Balance: {fox:.8f} | Profit: {netTreats:.8f} | Next Bet: {kitty:.8f}")
        
            scratchPad = round((fox + kitty), 8)
            litterbox = round((fox - kitty), 8)
        
            # UI updates via element interaction
            driver.find_element(By.ID, "pct_chance").clear()
            driver.find_element(By.ID, "pct_chance").send_keys(49.5)

            driver.find_element(By.ID, "pct_bet").clear()
            driver.find_element(By.ID, "pct_bet").send_keys(f"{kitty:.8f}")

            driver.find_element(By.ID, "a_lo").click()

            current_state = {
                "origiun": origiun, "fox": fox, "kitty": kitty, "fart": fart, "mile": mile, "mookie": mookie,
                "bear": bear, "scratchPad": scratchPad, "litterbox": litterbox, "lastLeap": lastLeap
            }
            save_state(current_state)

# ---------------------------
# MAIN LOOP WITH 'FOX' WATCHDOG
# ---------------------------
print("Bot started successfully. Running main loop...")
try:
    while True:
        # 1. Run step evaluations inside the main game tick
        runCatBot()
        
        # 2. Watchdog evaluate: Check if the tracked math position shifted
        if fox != LAST_FOX_VALUE:
            LAST_FOX_VALUE = fox
            LAST_FOX_CHANGE_TIMESTAMP = time.time()
        
        # 3. Check tracking window duration conditions
        time_since_fox_changed = time.time() - LAST_FOX_CHANGE_TIMESTAMP
        if time_since_fox_changed > 55:
            print(f"\n🚨 [WATCHDOG] 'fox' hasn't changed in {round(time_since_fox_changed, 1)} seconds! Page likely hung.")
            print("🔄 Refreshing page, but preserving your progress variables...")
            
            try:
                driver.refresh()
                # Resolve fresh Cloudflare IPs and apply them to firewall rules dynamically
                refresh_network_whitelist()

                # Trigger a browser refresh flow while locking current progression constants
                initialize_bot_process(keep_old_data=True)
                
                # Re-zero out verification values to prevent dynamic looping loops
                LAST_FOX_VALUE = fox
                LAST_FOX_CHANGE_TIMESTAMP = time.time() 
                print("✅ Reset complete. Resuming loop exactly where progression left off...")
            except Exception as e:
                print(f"⚠️ Error during recovery initialization: {e}. Retrying next cycle...")
                time.sleep(5) 

        time.sleep(0.01) 
except KeyboardInterrupt:
    print("\n🛑 Bot paused manually.")
finally:
    driver.quit()
