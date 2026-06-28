"""
Air Ticket Reservation System  -  Flask front-end (Part 3).

This file wires up every route/use-case required by the course project and
renders the matching template. ALL DATABASE LOGIC IS LEFT AS `TODO` STUBS so
you can drop in your own SQL (prepared statements) against your Part 2 schema.

How the front-end and back-end meet
-----------------------------------
* Each route already gathers the relevant form fields / query args into a
  Python dict and passes context variables to the template.
* Templates render lists/dicts you hand them (e.g. `flights`, `airplanes`,
  `reports`). They default to empty, so every page renders before you write
  any SQL.
* Replace each `# TODO(db): ...` block with your queries and set the variables
  the template expects (documented in the docstring of each route).

Session model
-------------
* session["user"]  -> username (email for customers, username for staff)
* session["role"]  -> "customer" or "staff"
* session["name"]  -> display name (optional)
Use the `@login_required` / `@role_required(...)` decorators to protect routes
on the server side (do NOT rely on hiding links only).

Security checklist (per the spec) — do these in your back-end:
* Authenticate with password = md5(y)  (the spec mandates md5).
* Use prepared statements / parameterized queries everywhere.
* Escape user text in templates (Jinja auto-escapes by default — keep it on).
"""

from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, jsonify, session, flash
)
from db import get_connection

app = Flask(__name__)
app.secret_key = "dev-secret-change-me"

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def role_required(role):
    """Server-side guard so a customer can't hit staff URLs and vice versa."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user" not in session:
                flash("Please log in first.", "error")
                return redirect(url_for("login"))
            if session.get("role") != role:
                flash("You are not authorized to access that page.", "error")
                return redirect(url_for("home"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


@app.context_processor
def inject_session():
    """Make the current user/role available to every template."""
    return {
        "current_user": session.get("user"),
        "current_role": session.get("role"),
        "current_name": session.get("name"),
    }


# Fetches and caches the staff member's airline so we don't query every request
def get_staff_airline():
    """Return the airline name for the logged-in staff member (cached in session)."""
    if "airline" in session:
        return session["airline"]
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT airline_name FROM Airline_Staff WHERE username = %s",
        (session["user"],)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        session["airline"] = row["airline_name"]
        return row["airline_name"]
    return None


# ===========================================================================
# Public pages (not logged in)
# ===========================================================================
@app.route("/")
def home():
    """Public home page: search box + register/login entry points."""
    return render_template("home.html")


@app.route("/search")
def search():
    """Public flight search (one-way or round-trip). No login required.

    Template expects:
        results       -> list of flight dicts (see flight_card macro fields)
        return_results-> list (round-trip return leg), optional
        searched      -> bool, whether a search was performed
    """
    f = {
        "trip_type": request.args.get("trip_type", "oneway"),
        "source": request.args.get("source", ""),       # city OR airport name
        "destination": request.args.get("destination", ""),
        "depart_date": request.args.get("depart_date", ""),
        "return_date": request.args.get("return_date", ""),
    }
    searched = bool(request.args)

    results, return_results = [], []
    if searched:
        pass

    return render_template(
        "search.html", f=f, results=results,
        return_results=return_results, searched=searched,
    )


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
@app.route("/register")
def register():
    """Landing page letting the visitor pick Customer or Staff registration."""
    return render_template("register.html")


@app.route("/register/customer", methods=["GET", "POST"])
def register_customer():
    if request.method == "POST":
        data = {
            "email": request.form.get("email", ""),
            "name": request.form.get("name", ""),
            "password": request.form.get("password", ""),
            "building_number": request.form.get("building_number", ""),
            "street": request.form.get("street", ""),
            "city": request.form.get("city", ""),
            "state": request.form.get("state", ""),
            "phone_number": request.form.get("phone_number", ""),
            "passport_number": request.form.get("passport_number", ""),
            "passport_expiration": request.form.get("passport_expiration", ""),
            "passport_country": request.form.get("passport_country", ""),
            "date_of_birth": request.form.get("date_of_birth", ""),
        }
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register_customer.html")


@app.route("/register/staff", methods=["GET", "POST"])
def register_staff():
    if request.method == "POST":
        data = {
            "username": request.form.get("username", ""),
            "password": request.form.get("password", ""),
            "first_name": request.form.get("first_name", ""),
            "last_name": request.form.get("last_name", ""),
            "date_of_birth": request.form.get("date_of_birth", ""),
            "email": request.form.get("email", ""),
            "airline_name": request.form.get("airline_name", ""),
            # multiple phone numbers come in as a list
            "phone_numbers": request.form.getlist("phone_number"),
        }
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT username FROM Airline_Staff WHERE username = %s",
            (data["username"],)
        )
        if cursor.fetchone():
            flash("Username already taken.", "error")
            cursor.close()
            conn.close()
            return render_template("register_staff.html")

        cursor.execute(
            "SELECT name FROM Airline WHERE name = %s",
            (data["airline_name"],)
        )
        if not cursor.fetchone():
            flash("Airline '" + data["airline_name"] + "' not found.", "error")
            cursor.close()
            conn.close()
            return render_template("register_staff.html")

        cursor.close()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Airline_Staff"
            " (username, airline_name, password, first_name, last_name, date_of_birth, email)"
            " VALUES (%s, %s, MD5(%s), %s, %s, %s, %s)",
            (data["username"], data["airline_name"], data["password"],
             data["first_name"], data["last_name"],
             data["date_of_birth"] or None, data["email"])
        )
        for phone in data["phone_numbers"]:
            phone = phone.strip()
            if phone:
                cursor.execute(
                    "INSERT INTO Staff_Phone (username, phone_number) VALUES (%s, %s)",
                    (data["username"], phone)
                )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register_staff.html")


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role", "customer")     # "customer" | "staff"
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        authenticated = False
        display_name = username
        airline = None

        # Staff auth: verify username + MD5 password against Airline_Staff table
        if role == "staff":
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT username, first_name, last_name, airline_name"
                " FROM Airline_Staff WHERE username = %s AND password = MD5(%s)",
                (username, password)
            )
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                authenticated = True
                display_name = row["first_name"] + " " + row["last_name"]
                airline = row["airline_name"]

        elif role == "customer":
            conn = get_connection()
            cursor = conn.cursor()
            query = """
            SELECT email FROM Customer
            WHERE email = %s AND password = MD5(%s)
            """
            cursor.execute(query, (username, password))
            if cursor.fetchone() is not None:
                authenticated = True
            cursor.close()
            conn.close()

        if authenticated:
            session.clear()
            session["user"] = username
            session["role"] = role
            session["name"] = display_name
            if airline:
                session["airline"] = airline
            return redirect(url_for("customer_home" if role == "customer"
                                    else "staff_home"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return render_template("goodbye.html")


# ===========================================================================
# Customer use cases
# ===========================================================================
@app.route("/customer")
@role_required("customer")
def customer_home():
    """Customer home page. Optionally show their upcoming flights."""
    upcoming = []
    return render_template("customer/home.html", upcoming=upcoming)


@app.route("/customer/my-flights")
@role_required("customer")
def customer_my_flights():
    """View My Flights — default = future flights; optional filters."""
    f = {
        "scope": request.args.get("scope", "future"),
        "source": request.args.get("source", ""),
        "destination": request.args.get("destination", ""),
        "start_date": request.args.get("start_date", ""),
        "end_date": request.args.get("end_date", ""),
    }
    flights = []
    return render_template("customer/my_flights.html", flights=flights, f=f)


@app.route("/customer/purchase", methods=["GET", "POST"])
@role_required("customer")
def customer_purchase():
    """Purchase a ticket for a chosen flight.

    GET  : show the form (flight pre-filled from query args if provided).
    POST : validate seat availability, insert ticket + payment, then confirm.
    """
    if request.method == "POST":
        data = {
            "airline_name": request.form.get("airline_name", ""),
            "flight_number": request.form.get("flight_number", ""),
            "flight_date": request.form.get("flight_date", ""),
            "card_type": request.form.get("card_type", ""),     # credit | debit
            "card_number": request.form.get("card_number", ""),
            "name_on_card": request.form.get("name_on_card", ""),
            "expiration_date": request.form.get("expiration_date", ""),
        }
        # TODO(db): check the plane still has room (booked < capacity);
        #           if full -> flash error & re-render. Otherwise INSERT ticket
        #           (with purchase date/time) for session["user"].
        flash("Ticket purchased successfully!", "success")
        return redirect(url_for("customer_my_flights"))

    flight = {
        "airline_name": request.args.get("airline_name", ""),
        "flight_number": request.args.get("flight_number", ""),
        "flight_date": request.args.get("flight_date", ""),
        "base_price": request.args.get("base_price", ""),
    }
    return render_template("customer/purchase.html", flight=flight)


@app.route("/customer/rate", methods=["GET", "POST"])
@role_required("customer")
def customer_rate():
    """Rate & comment on a previously-taken flight (for the logged-in airline)."""
    if request.method == "POST":
        data = {
            "airline_name": request.form.get("airline_name", ""),
            "flight_number": request.form.get("flight_number", ""),
            "flight_date": request.form.get("flight_date", ""),
            "rating": request.form.get("rating", ""),      # 1..5
            "comment": request.form.get("comment", ""),
        }
        # TODO(db): ensure the customer actually took this past flight, then
        #           INSERT/UPDATE the rating+comment.
        flash("Thanks for your feedback!", "success")
        return redirect(url_for("customer_rate"))

    past_flights = []
    # TODO(db): past_flights = flights the customer already took (eligible to rate).
    return render_template("customer/rate.html", past_flights=past_flights)


# ===========================================================================
# Airline Staff use cases
# ===========================================================================
@app.route("/staff")
@role_required("staff")
def staff_home():
    """Staff home — default: future flights for their airline (next 30 days)."""
    # Shows only flights departing within the next 30 days for the staff's airline
    airline = get_staff_airline()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT airline_name, flight_number, departure_airport, departure_datetime,"
        " arrival_airport, arrival_datetime, price AS base_price, status"
        " FROM Flight"
        " WHERE airline_name = %s"
        "   AND departure_datetime > NOW()"
        "   AND departure_datetime <= DATE_ADD(NOW(), INTERVAL 30 DAY)"
        " ORDER BY departure_datetime",
        (airline,)
    )
    flights = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("staff/home.html", flights=flights)


@app.route("/staff/flights")
@role_required("staff")
def staff_view_flights():
    """View flights with filters; optionally drill into a flight's customers.

    Template expects: flights (list), f (filters), customers (list, optional),
                      selected_flight (dict, optional).
    """
    f = {
        "scope": request.args.get("scope", "future"),   # future|past|all|range
        "start_date": request.args.get("start_date", ""),
        "end_date": request.args.get("end_date", ""),
        "source": request.args.get("source", ""),
        "destination": request.args.get("destination", ""),
        "flight_number": request.args.get("flight_number", ""),
    }
    airline = get_staff_airline()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if f["scope"] == "past":
        cursor.execute(
            "SELECT airline_name, flight_number, departure_airport, departure_datetime,"
            " arrival_airport, arrival_datetime, price AS base_price, status"
            " FROM Flight WHERE airline_name = %s AND departure_datetime < NOW()"
            " ORDER BY departure_datetime DESC",
            (airline,)
        )
    elif f["scope"] == "all":
        cursor.execute(
            "SELECT airline_name, flight_number, departure_airport, departure_datetime,"
            " arrival_airport, arrival_datetime, price AS base_price, status"
            " FROM Flight WHERE airline_name = %s ORDER BY departure_datetime",
            (airline,)
        )
    elif f["scope"] == "range" and f["start_date"] and f["end_date"]:
        cursor.execute(
            "SELECT airline_name, flight_number, departure_airport, departure_datetime,"
            " arrival_airport, arrival_datetime, price AS base_price, status"
            " FROM Flight WHERE airline_name = %s"
            " AND DATE(departure_datetime) BETWEEN %s AND %s"
            " ORDER BY departure_datetime",
            (airline, f["start_date"], f["end_date"])
        )
    else:
        cursor.execute(
            "SELECT airline_name, flight_number, departure_airport, departure_datetime,"
            " arrival_airport, arrival_datetime, price AS base_price, status"
            " FROM Flight WHERE airline_name = %s AND departure_datetime > NOW()"
            " ORDER BY departure_datetime",
            (airline,)
        )
    flights = cursor.fetchall()

    # If a flight number is provided, also fetch the passenger list for that flight
    customers = []
    selected_flight = None
    if f["flight_number"]:
        if f["start_date"]:
            cursor.execute(
                "SELECT flight_number, departure_datetime, departure_airport, arrival_airport"
                " FROM Flight WHERE airline_name = %s AND flight_number = %s"
                " AND DATE(departure_datetime) = %s LIMIT 1",
                (airline, f["flight_number"], f["start_date"])
            )
        else:
            cursor.execute(
                "SELECT flight_number, departure_datetime, departure_airport, arrival_airport"
                " FROM Flight WHERE airline_name = %s AND flight_number = %s"
                " ORDER BY departure_datetime LIMIT 1",
                (airline, f["flight_number"])
            )
        selected_flight = cursor.fetchone()
        if selected_flight:
            cursor.execute(
                "SELECT c.name, c.email, t.ID AS ticket_id, t.purchase_datetime"
                " FROM Ticket t JOIN Customer c ON t.customer_email = c.email"
                " WHERE t.airline_name = %s AND t.flight_number = %s"
                " AND t.departure_datetime = %s",
                (airline, f["flight_number"], selected_flight["departure_datetime"])
            )
            customers = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template(
        "staff/view_flights.html", flights=flights, f=f,
        customers=customers, selected_flight=selected_flight,
    )


@app.route("/staff/flights/create", methods=["GET", "POST"])
@role_required("staff")
def staff_create_flight():
    if request.method == "POST":
        data = {
            "flight_number": request.form.get("flight_number", ""),
            "departure_airport": request.form.get("departure_airport", ""),
            "departure_datetime": request.form.get("departure_datetime", ""),
            "arrival_airport": request.form.get("arrival_airport", ""),
            "arrival_datetime": request.form.get("arrival_datetime", ""),
            "base_price": request.form.get("base_price", ""),
            "airplane_id": request.form.get("airplane_id", ""),
            "status": request.form.get("status", "on-time"),
        }
        airline = get_staff_airline()
        dep_dt = data["departure_datetime"].replace("T", " ")
        arr_dt = data["arrival_datetime"].replace("T", " ")

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        # Prevent duplicate flights with the same number and departure time
        query = """
            SELECT 1 FROM Flight
            WHERE airline_name = %s AND flight_number = %s AND departure_datetime = %s
        """
        cursor.execute(query, (airline, data["flight_number"], dep_dt))
        if cursor.fetchone():
            flash("A flight with that number and departure time already exists.", "error")
            cursor.close()
            conn.close()
            return redirect(url_for("staff_create_flight"))

        cursor.close()
        cursor = conn.cursor()
        query = """
            INSERT INTO Flight
                (airline_name, flight_number, departure_datetime, arrival_datetime,
                 price, airplane_id, departure_airport, arrival_airport, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            airline, data["flight_number"], dep_dt, arr_dt,
            data["base_price"], data["airplane_id"],
            data["departure_airport"], data["arrival_airport"], data["status"]
        ))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Flight created successfully.", "success")
        return redirect(url_for("staff_view_flights"))

    airline = get_staff_airline()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT name, city, country FROM Airport ORDER BY name")
    airports = cursor.fetchall()

    query = """
        SELECT ID AS airplane_id, num_seats, company AS manufacturer, age
        FROM Airplane WHERE airline_name = %s ORDER BY ID
    """
    cursor.execute(query, (airline,))
    airplanes = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template(
        "staff/create_flight.html", airports=airports, airplanes=airplanes,
    )


@app.route("/staff/flights/status", methods=["GET", "POST"])
@role_required("staff")
def staff_change_status():
    if request.method == "POST":
        data = {
            "flight_number": request.form.get("flight_number", ""),
            "flight_date": request.form.get("flight_date", ""),
            "status": request.form.get("status", ""),     # on-time | delayed
        }
        airline = get_staff_airline()
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            UPDATE Flight SET status = %s
            WHERE airline_name = %s AND flight_number = %s AND departure_datetime = %s
        """
        cursor.execute(query, (
            data["status"], airline, data["flight_number"], data["flight_date"]
        ))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Flight " + data["flight_number"] + " updated to " + data["status"] + ".", "success")
        return redirect(url_for("staff_change_status"))

    airline = get_staff_airline()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT flight_number, departure_airport, arrival_airport,
               departure_datetime, status
        FROM Flight
        WHERE airline_name = %s
        ORDER BY departure_datetime
    """
    cursor.execute(query, (airline,))
    flights = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("staff/change_status.html", flights=flights)


@app.route("/staff/airplanes", methods=["GET", "POST"])
@role_required("staff")
def staff_add_airplane():
    if request.method == "POST":
        data = {
            "airplane_id": request.form.get("airplane_id", ""),
            "num_seats": request.form.get("num_seats", ""),
            "manufacturer": request.form.get("manufacturer", ""),
            "age": request.form.get("age", ""),
        }
        airline = get_staff_airline()
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        # Prevent duplicate airplane IDs within the same airline
        query = """
            SELECT 1 FROM Airplane WHERE airline_name = %s AND ID = %s
        """
        cursor.execute(query, (airline, data["airplane_id"]))
        if cursor.fetchone():
            flash("An airplane with that ID already exists for your airline.", "error")
            cursor.close()
            conn.close()
            return redirect(url_for("staff_add_airplane"))

        cursor.close()
        cursor = conn.cursor()
        query = """
            INSERT INTO Airplane (airline_name, ID, num_seats, company, age)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            airline, data["airplane_id"], data["num_seats"],
            data["manufacturer"], data["age"]
        ))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Airplane added successfully.", "success")

    airline = get_staff_airline()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT ID AS airplane_id, num_seats, company AS manufacturer, age
        FROM Airplane WHERE airline_name = %s ORDER BY ID
    """
    cursor.execute(query, (airline,))
    airplanes = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("staff/add_airplane.html", airplanes=airplanes)


@app.route("/staff/ratings")
@role_required("staff")
def staff_ratings():
    """Per-flight average rating + all comments for this airline's flights."""
    airline = get_staff_airline()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Get average rating per flight, then fetch individual comments for each
    query = """
        SELECT f.flight_number, f.departure_datetime AS flight_date,
               AVG(r.rating) AS avg_rating
        FROM Flight f
        JOIN Review r ON f.airline_name = r.airline_name
                     AND f.flight_number = r.flight_number
                     AND f.departure_datetime = r.departure_datetime
        WHERE f.airline_name = %s
        GROUP BY f.flight_number, f.departure_datetime
        ORDER BY f.departure_datetime DESC
    """
    cursor.execute(query, (airline,))
    rows = cursor.fetchall()

    ratings = []
    for fl in rows:
        query = """
            SELECT c.name AS customer, r.rating, r.comment
            FROM Review r
            JOIN Customer c ON r.customer_email = c.email
            WHERE r.airline_name = %s AND r.flight_number = %s
              AND r.departure_datetime = %s
        """
        cursor.execute(query, (airline, fl["flight_number"], fl["flight_date"]))
        comments = cursor.fetchall()
        ratings.append({
            "flight_number": fl["flight_number"],
            "flight_date":   fl["flight_date"],
            "avg_rating":    float(fl["avg_rating"]),
            "comments":      list(comments),
        })

    cursor.close()
    conn.close()
    return render_template("staff/ratings.html", ratings=ratings)


@app.route("/staff/reports")
@role_required("staff")
def staff_reports():
    """Sales reports: totals by date range + month-wise tickets for a chart.

    Template expects:
        total_sales   -> number (for the selected range)
        f             -> {range, start_date, end_date}
        monthly       -> list of {month: "2026-01", count: N, revenue: X}
    """
    f = {
        "range": request.args.get("range", "last_year"),  # last_month|last_year|custom
        "start_date": request.args.get("start_date", ""),
        "end_date": request.args.get("end_date", ""),
    }
    airline = get_staff_airline()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if f["range"] == "last_month":
        date_condition = "DATE(t.purchase_datetime) >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)"
        params = (airline,)
    elif f["range"] == "custom" and f["start_date"] and f["end_date"]:
        date_condition = "DATE(t.purchase_datetime) BETWEEN %s AND %s"
        params = (airline, f["start_date"], f["end_date"])
    else:
        date_condition = "DATE(t.purchase_datetime) >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)"
        params = (airline,)

    # Total tickets sold and revenue for the selected date range
    query = """
        SELECT COUNT(*) AS cnt, SUM(f.price) AS total_revenue
        FROM Ticket t
        JOIN Flight f ON t.airline_name = f.airline_name
                     AND t.flight_number = f.flight_number
                     AND t.departure_datetime = f.departure_datetime
        WHERE t.airline_name = %s AND """ + date_condition
    cursor.execute(query, params)
    row = cursor.fetchone()
    total_sales = row["cnt"] if row else 0
    total_revenue = float(row["total_revenue"]) if row and row["total_revenue"] else 0.0

    # Monthly breakdown for the bar chart — month_sort keeps chronological order
    query = """
        SELECT DATE_FORMAT(t.purchase_datetime, '%M %Y') AS month,
               DATE_FORMAT(t.purchase_datetime, '%Y-%m') AS month_sort,
               COUNT(*) AS count,
               SUM(f.price) AS revenue
        FROM Ticket t
        JOIN Flight f ON t.airline_name = f.airline_name
                     AND t.flight_number = f.flight_number
                     AND t.departure_datetime = f.departure_datetime
        WHERE t.airline_name = %s AND """ + date_condition + """
        GROUP BY DATE_FORMAT(t.purchase_datetime, '%Y-%m'),
                 DATE_FORMAT(t.purchase_datetime, '%M %Y')
        ORDER BY DATE_FORMAT(t.purchase_datetime, '%Y-%m')
    """
    cursor.execute(query, params)
    monthly = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template(
        "staff/reports.html", f=f, total_sales=total_sales,
        total_revenue=total_revenue, monthly=monthly,
    )


@app.route("/staff/flights/detail")
@role_required("staff")
def staff_flight_detail():
    """Full detail view for a single flight: info + airplane + passengers."""
    # Linked from the home dashboard — shows everything about one flight in one screen
    airline = get_staff_airline()
    flight_number = request.args.get("flight_number", "")
    departure_datetime = request.args.get("departure_datetime", "")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT f.flight_number, f.departure_airport, f.arrival_airport,
               f.departure_datetime, f.arrival_datetime,
               f.price AS base_price, f.status,
               a.ID AS airplane_id, a.num_seats, a.company AS manufacturer, a.age
        FROM Flight f
        LEFT JOIN Airplane a ON f.airplane_id = a.ID AND f.airline_name = a.airline_name
        WHERE f.airline_name = %s AND f.flight_number = %s AND f.departure_datetime = %s
    """
    cursor.execute(query, (airline, flight_number, departure_datetime))
    flight = cursor.fetchone()

    if not flight:
        flash("Flight not found.", "error")
        cursor.close()
        conn.close()
        return redirect(url_for("staff_home"))

    query = """
        SELECT c.name, c.email, t.ID AS ticket_id, t.purchase_datetime
        FROM Ticket t
        JOIN Customer c ON t.customer_email = c.email
        WHERE t.airline_name = %s AND t.flight_number = %s AND t.departure_datetime = %s
        ORDER BY t.purchase_datetime
    """
    cursor.execute(query, (airline, flight_number, departure_datetime))
    passengers = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("staff/flight_detail.html", flight=flight, passengers=passengers)


if __name__ == "__main__":
    app.run(debug=True)
