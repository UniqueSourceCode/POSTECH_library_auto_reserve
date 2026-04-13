import requests
import time
import os

# ============================================================
# CONFIGURATION — edit these if needed
# ============================================================

BASE_URL = "https://zzim.postech.ac.kr/smufu-api/api"
ROOM_ID = 6        # Plora 4층
SEAT_ID = 900      # Seat 22
SEAT_CODE = "22"
MAX_RETRIES = 5    # how many times to retry if reservation fails
RETRY_DELAY = 3    # seconds between retries

# ============================================================
# STEP 1 — LOGIN
# ============================================================

def login(session, pni_token):
    print("\n[1] Logging in...")
    sso_url = (
        f"https://zzim.postech.ac.kr/smufu-api/sso-login"
        f"?isMobile=N&autoLogin=N&authInfo=michael1209&pniToken={pni_token}"
    )

    # Follow redirects
    r = session.get(sso_url, allow_redirects=True)
    final_url = r.url

    # Extract access token from the final URL
    # Final URL looks like: /#/sso-login/S_xxxxx?autoLogin=N&pniToken=...
    token = None
    if "/sso-login/" in final_url:
        after = final_url.split("/sso-login/")[1]
        token = after.split("?")[0]

    if token and token.startswith("S_"):
        print(f"    v SSO login successful (token: {token[:12]}...)")

        # Validate using the correct header name found in the site's JS config
        session.headers.update({"pyxis-Auth-Token": token})
        r2 = session.get(f"{BASE_URL}/validate")
        data = r2.json()
        if data.get("success"):
            name = data["data"]["name"]
            # Use the fresh accessToken returned by validate for all further requests
            fresh_token = data["data"].get("accessToken", token)
            session.headers.update({"pyxis-Auth-Token": fresh_token})
            print(f"    v Logged in as {name}")
            return True

        print(f"    x Authentication failed: {data.get('message')} (code: {data.get('code')})")
        return False
    else:
        print(f"    x Could not extract token from URL: {final_url}")
        return False

# ============================================================
# STEP 2 — CHECK IF ALREADY RESERVED
# ============================================================

def get_my_reservation(session):
    print("\n[2] Checking current reservation...")
    r = session.get(f"{BASE_URL}/pc/my-ticket")
    data = r.json()
    if data.get("success") and data["data"]["totalCount"] > 0:
        ticket = data["data"]["list"][0]
        seat_code = ticket["seat"]["code"]
        reservation_id = ticket["id"]
        state = ticket["seatCirculationState"]["code"]
        print(f"    v Found reservation -- Seat {seat_code}, ID: {reservation_id}, State: {state}")
        return reservation_id, seat_code, state
    else:   
        print("    v No current reservation found")
        return None, None, None

# ============================================================
# STEP 3 — CANCEL RESERVATION
# ============================================================

def cancel_reservation(session, reservation_id, state):
    print(f"\n[3] Cancelling reservation {reservation_id} (state: {state})...")
    endpoint = "cancel" if state == "TEMP_CHARGE" else "return"
    r = session.post(f"{BASE_URL}/pc/seat-charge/{reservation_id}/{endpoint}")
    data = r.json()
    if data.get("success"):
        print("    v Reservation cancelled successfully")
        return True
    else:
        print(f"    x Failed to cancel: {data.get('message')}")
        return False

# ============================================================
# STEP 4 — CHECK IF SEAT 22 IS AVAILABLE
# ============================================================

def is_seat_available(session):
    r = session.get(f"{BASE_URL}/pc/rooms-at-seat/{ROOM_ID}/seats")
    data = r.json()
    if data.get("success"):
        seat = data["data"].get(SEAT_CODE)
        if seat:
            return seat["isAvailable"]
    return False

# ============================================================
# STEP 5 — RESERVE SEAT 22
# ============================================================

def reserve_seat(session):
    print(f"\n[4] Reserving seat {SEAT_CODE}...")
    r = session.post(f"{BASE_URL}/pc/seats/{SEAT_ID}/charge-temporarily")
    data = r.json()
    if data.get("success"):
        new_id = data["data"]["id"]
        state = data["data"]["seatCirculationState"]["code"]
        begin = data["data"]["beginTime"]
        end = data["data"]["endTime"]
        print(f"    v Reservation successful!")
        print(f"      Reservation ID : {new_id}")
        print(f"      State          : {state}")
        print(f"      Begin          : {begin}")
        print(f"      End            : {end}")
        return True
    else:
        print(f"    x Reservation failed: {data.get('message')} ({data.get('code')})")
        return False

# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 50)
    print("  POSTECH Library Auto-Reservation Script")
    print("=" * 50)

    pni_token = os.environ.get("PNI_TOKEN")
    if not pni_token:
        token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pniToken.txt")
        if os.path.exists(token_file):
            with open(token_file) as f:
                pni_token = f.read().strip()
            print(f"\nLoaded pniToken from pniToken.txt")
        else:
            pni_token = input("\nPaste your pniToken here:\n> ").strip()

    if not pni_token:
        print("No token provided. Exiting.")
        return

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    })

    # Step 1 - Login
    if not login(session, pni_token):
        print("\nLogin failed. Please get a fresh pniToken and try again.")
        return

    # Step 2 - Check existing reservation
    reservation_id, seat_code, state = get_my_reservation(session)

    # Step 3 - Cancel if already reserved
    if reservation_id:
        print(f"\n    Seat {seat_code} is currently reserved by you.")
        cancelled = cancel_reservation(session, reservation_id, state)
        if not cancelled:
            print("\nCould not cancel existing reservation. Exiting.")
            return
        print("    Waiting for seat to reset after cancellation...")
        time.sleep(5)

    # Step 4 & 5 - Reserve seat 22 with retries
    print(f"\n[4] Attempting to reserve seat {SEAT_CODE} (max {MAX_RETRIES} tries)...")
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n    Attempt {attempt}/{MAX_RETRIES}")

        if reserve_seat(session):
            print("\n" + "=" * 50)
            print("  SUCCESS -- Seat reserved!")
            print("=" * 50)
            return
        else:
            print(f"    Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

    print("\n" + "=" * 50)
    print("  FAILED -- Could not reserve seat after all attempts.")
    print("=" * 50)

if __name__ == "__main__":
    main()