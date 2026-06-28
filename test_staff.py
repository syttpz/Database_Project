"""
Staff smoke tests — run with:  python3 test_staff.py
Tests DB connection and every major staff query without starting Flask.
All tests use the sample data inserted during DB setup.
"""

from db import get_connection

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []

def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    results.append(condition)


# ---------------------------------------------------------------------------
print("\n=== 1. DB Connection ===")
try:
    conn = get_connection()
    conn.close()
    check("Connect to airline_db", True)
except Exception as e:
    check("Connect to airline_db", False, str(e))
    print("Cannot continue without DB connection.")
    exit(1)


# ---------------------------------------------------------------------------
print("\n=== 2. Staff Login (MD5 password check) ===")
conn = get_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute(
    "SELECT username, first_name, last_name, airline_name"
    " FROM Airline_Staff WHERE username = %s AND password = MD5(%s)",
    ("manager", "admin123")
)
row = cursor.fetchone()
check("Login with correct credentials", row is not None)
if row:
    check("Airline stored in result", "airline_name" in row, row.get("airline_name"))
cursor.execute(
    "SELECT 1 FROM Airline_Staff WHERE username = %s AND password = MD5(%s)",
    ("manager", "wrongpassword")
)
check("Login with wrong password returns nothing", cursor.fetchone() is None)
cursor.close()
conn.close()


# ---------------------------------------------------------------------------
print("\n=== 3. Staff Home — next 30-day flights ===")
conn = get_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute(
    "SELECT flight_number, departure_datetime, status, price AS base_price"
    " FROM Flight WHERE airline_name = %s"
    " AND departure_datetime > NOW()"
    " AND departure_datetime <= DATE_ADD(NOW(), INTERVAL 30 DAY)"
    " ORDER BY departure_datetime",
    ("JetBlue",)
)
flights = cursor.fetchall()
check("Home query runs", True)
check("Returns list", isinstance(flights, list), f"{len(flights)} flight(s)")
cursor.close()
conn.close()


# ---------------------------------------------------------------------------
print("\n=== 4. View Flights — future / past / all ===")
conn = get_connection()
cursor = conn.cursor(dictionary=True)

cursor.execute(
    "SELECT flight_number, departure_datetime, price AS base_price, status"
    " FROM Flight WHERE airline_name = %s AND departure_datetime > NOW()"
    " ORDER BY departure_datetime",
    ("JetBlue",)
)
check("Future flights query", True, f"{len(cursor.fetchall())} row(s)")

cursor.execute(
    "SELECT flight_number FROM Flight WHERE airline_name = %s"
    " AND departure_datetime < NOW()",
    ("JetBlue",)
)
cursor.fetchall()
check("Past flights query runs", True)

cursor.execute(
    "SELECT flight_number FROM Flight WHERE airline_name = %s ORDER BY departure_datetime",
    ("JetBlue",)
)
all_flights = cursor.fetchall()
check("All flights query runs", True, f"{len(all_flights)} total")
cursor.close()
conn.close()


# ---------------------------------------------------------------------------
print("\n=== 5. Passengers on a flight ===")
conn = get_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute(
    "SELECT flight_number, departure_datetime FROM Flight"
    " WHERE airline_name = %s ORDER BY departure_datetime LIMIT 1",
    ("JetBlue",)
)
fl = cursor.fetchone()
if fl:
    cursor.execute(
        "SELECT c.name, c.email, t.ID AS ticket_id, t.purchase_datetime"
        " FROM Ticket t JOIN Customer c ON t.customer_email = c.email"
        " WHERE t.airline_name = %s AND t.flight_number = %s AND t.departure_datetime = %s",
        ("JetBlue", fl["flight_number"], fl["departure_datetime"])
    )
    pax = cursor.fetchall()
    check("Passenger query runs", True, f"{len(pax)} passenger(s) on {fl['flight_number']}")
else:
    check("Passenger query — no flights found to test against", False)
cursor.close()
conn.close()


# ---------------------------------------------------------------------------
print("\n=== 6. Create Flight — airplane & airport dropdowns ===")
conn = get_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute("SELECT name, city, country FROM Airport ORDER BY name")
airports = cursor.fetchall()
check("Airports list", len(airports) > 0, f"{len(airports)} airport(s)")

cursor.execute(
    "SELECT ID AS airplane_id, num_seats, company AS manufacturer, age"
    " FROM Airplane WHERE airline_name = %s ORDER BY ID",
    ("JetBlue",)
)
planes = cursor.fetchall()
check("Airplanes list for airline", len(planes) > 0, f"{len(planes)} plane(s)")
cursor.close()
conn.close()


# ---------------------------------------------------------------------------
print("\n=== 7. Add Airplane — duplicate check ===")
conn = get_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute(
    "SELECT 1 FROM Airplane WHERE airline_name = %s AND ID = %s",
    ("JetBlue", 101)
)
check("Duplicate airplane check finds existing ID 101", cursor.fetchone() is not None)
cursor.execute(
    "SELECT 1 FROM Airplane WHERE airline_name = %s AND ID = %s",
    ("JetBlue", 9999)
)
check("Duplicate check returns nothing for non-existent ID", cursor.fetchone() is None)
cursor.close()
conn.close()


# ---------------------------------------------------------------------------
print("\n=== 8. Change Status — flight dropdown ===")
conn = get_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute(
    "SELECT flight_number, departure_airport, arrival_airport, departure_datetime, status"
    " FROM Flight WHERE airline_name = %s ORDER BY departure_datetime",
    ("JetBlue",)
)
rows = cursor.fetchall()
check("Status dropdown query runs", len(rows) > 0, f"{len(rows)} flight(s)")
if rows:
    check("Status field present", "status" in rows[0], rows[0].get("status"))
cursor.close()
conn.close()


# ---------------------------------------------------------------------------
print("\n=== 9. Ratings ===")
conn = get_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute(
    "SELECT f.flight_number, f.departure_datetime AS flight_date,"
    " AVG(r.rating) AS avg_rating"
    " FROM Flight f"
    " JOIN Review r ON f.airline_name = r.airline_name"
    "              AND f.flight_number = r.flight_number"
    "              AND f.departure_datetime = r.departure_datetime"
    " WHERE f.airline_name = %s"
    " GROUP BY f.flight_number, f.departure_datetime",
    ("JetBlue",)
)
ratings = cursor.fetchall()
check("Ratings aggregate query runs", True, f"{len(ratings)} rated flight(s)")
cursor.close()
conn.close()


# ---------------------------------------------------------------------------
print("\n=== 10. Reports — total sales & monthly breakdown ===")
conn = get_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute(
    "SELECT COUNT(*) AS cnt FROM Ticket t"
    " WHERE t.airline_name = %s"
    " AND DATE(t.purchase_datetime) >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)",
    ("JetBlue",)
)
row = cursor.fetchone()
check("Total sales count query runs", row is not None, f"{row['cnt']} ticket(s)" if row else "")

cursor.execute(
    "SELECT DATE_FORMAT(t.purchase_datetime, '%Y-%m') AS month,"
    " COUNT(*) AS count, SUM(f.price) AS revenue"
    " FROM Ticket t"
    " JOIN Flight f ON t.airline_name = f.airline_name"
    "              AND t.flight_number = f.flight_number"
    "              AND t.departure_datetime = f.departure_datetime"
    " WHERE t.airline_name = %s"
    " AND DATE(t.purchase_datetime) >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)"
    " GROUP BY DATE_FORMAT(t.purchase_datetime, '%Y-%m') ORDER BY month",
    ("JetBlue",)
)
monthly = cursor.fetchall()
check("Monthly breakdown query runs", True, f"{len(monthly)} month(s) of data")
cursor.close()
conn.close()


# ---------------------------------------------------------------------------
print("\n=== 11. Staff Registration — airline exists check ===")
conn = get_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute("SELECT name FROM Airline WHERE name = %s", ("JetBlue",))
check("Existing airline (JetBlue) found", cursor.fetchone() is not None)
cursor.execute("SELECT name FROM Airline WHERE name = %s", ("FakeAir",))
check("Non-existent airline returns nothing (registration will be rejected)", cursor.fetchone() is None)
cursor.close()
conn.close()


# ---------------------------------------------------------------------------
passed = sum(results)
total = len(results)
print(f"\n{'='*40}")
print(f"Results: {passed}/{total} checks passed")
if passed == total:
    print("All checks passed — staff backend looks healthy.")
else:
    print(f"{total - passed} check(s) failed — review the output above.")
print()
