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

#db connection
from db import get_connection

app = Flask(__name__)
# Required for session + flash(). Use a fixed dev key (override in production).
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

    #one way, round trip
    results, return_results = [], []

    if searched:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT f.*,
            f.price AS base_price,
            dep.city AS departure_city,
            arr.city AS arrival_city
        FROM Flight AS f
            JOIN Airport AS dep ON f.departure_airport = dep.name
            JOIN Airport AS arr ON f.arrival_airport = arr.name
        WHERE dep.city = %s
            AND arr.city = %s
            AND DATE(f.departure_datetime) = %s
        """

        cursor.execute(query, (
            f["source"],
            f["destination"],
            f["depart_date"]
        ))

        results = cursor.fetchall()

        if f["trip_type"] == "round":
            # swapped destination and source
            cursor.execute(query, (
                f["destination"],
                f["source"],
                f["return_date"]
            ))
            return_results = cursor.fetchall()

        #close connection
        cursor.close()
        conn.close()
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
        # TODO(db): INSERT customer (store md5(password)). Handle duplicate email.
        # On success:
        conn = get_connection()
        cursor = conn.cursor()

        #TODO: check if email already registered
        query = """
        SELECT email
        FROM Customer
        WHERE email = %s
        """
        cursor.execute(query, (data["email"],))
        registered = cursor.fetchone()
        if registered:
            flash("User Already Exist. Please Login.", "failed")
            return render_template("register_customer.html")

        query = """
        INSERT INTO Customer(
            email,
            name,
            password,
            building_number,
            street,
            city,
            state,
            phone_number,
            passport_number,
            passport_expiration,
            passport_country,
            date_of_birth
        )
        values (%s, %s, MD5(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(query, (
            data["email"],
            data["name"],
            data["password"],
            data["building_number"],
            data["street"],
            data["city"],
            data["state"],
            data["phone_number"],
            data["passport_number"],
            data["passport_expiration"],
            data["passport_country"],
            data["date_of_birth"]
        ))
        conn.commit()

        cursor.close()
        conn.close()

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
        # TODO(db): INSERT airline staff (+ phone numbers, store md5(password)).
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

        # TODO(db): look up the user in the right table and compare
        #           password against md5(y). For example:
        #   if role == "customer": row = SELECT ... FROM customer
        #       WHERE email=%s AND password=MD5(%s)
        #   else: row = SELECT ... FROM airline_staff
        #       WHERE username=%s AND password=MD5(%s)
        conn = get_connection()
        cursor = conn.cursor()

        if role == "customer":
            query = """
            SELECT email 
            FROM Customer
            WHERE email = %s AND password = MD5(%s)  
            """
        else:
            query = """
            SELECT email 
            FROM Airline_Staff
            WHERE email = %s AND password = MD5(%s)  
            """
        cursor.execute(query, (
            username,
            password
        ))

        if cursor.fetchone() == None:
            authenticated = False
        else:
            authenticated = True

        cursor.close()
        conn.close()

        display_name = username

        if authenticated:
            session.clear()
            session["user"] = username
            session["role"] = role
            session["name"] = display_name
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
    # TODO(db): upcoming = future tickets/flights for session["user"].
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT f.*, f.price AS base_price
    FROM Ticket t
        JOIN Flight f on t.airline_name = f.airline_name
        AND t.flight_number = f.flight_number
        AND t.departure_datetime = f.departure_datetime
    WHERE t.customer_email = %s
    AND t.departure_datetime >= NOW();
    """
    cursor.execute(query, (session["user"],))
    upcoming = cursor.fetchall()

    cursor.close()
    conn.close()
    
    return render_template("customer/home.html", upcoming=upcoming)


@app.route("/customer/my-flights")
@role_required("customer")
def customer_my_flights():
    """View My Flights — default = future flights; optional filters.

    Template expects: flights (list), f (filter dict), scope.
    """
    f = {
        "scope": request.args.get("scope", "future"),   # future | past | all
        "source": request.args.get("source", ""),
        "destination": request.args.get("destination", ""),
        "start_date": request.args.get("start_date", ""),
        "end_date": request.args.get("end_date", ""),
    }
    flights = []
    # TODO(db): SELECT flights the customer bought tickets for, filtered by f.
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT f.*, f.price AS base_price
    FROM Ticket t
        JOIN Flight f ON t.airline_name = f.airline_name
        AND t.flight_number = f.flight_number
        AND t.departure_datetime = f.departure_datetime
        JOIN Airport dep ON f.departure_airport = dep.name
        JOIN Airport arr ON f.arrival_airport = arr.name
    WHERE t.customer_email = %s
    """
    params = [session["user"]]

    # Optional filters: only applied when the user actually supplied them.
    if f["source"]:
        query += " AND (f.departure_airport = %s OR dep.city = %s)"
        params += [f["source"], f["source"]]
    if f["destination"]:
        query += " AND (f.arrival_airport = %s OR arr.city = %s)"
        params += [f["destination"], f["destination"]]
    if f["start_date"]:
        query += " AND f.departure_datetime >= %s"
        params.append(f["start_date"])
    if f["end_date"]:
        query += " AND f.departure_datetime <= %s"
        params.append(f["end_date"])

    if f["scope"] == "future":
        query += " AND f.departure_datetime >= NOW()"
    elif f["scope"] == "past":
        query += " AND f.departure_datetime < NOW()"

    query += " ORDER BY f.departure_datetime"
    cursor.execute(query, tuple(params))

    flights = cursor.fetchall()

    cursor.close()
    conn.close()

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
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        #capacity
        query = """
        SELECT
            a.num_seats,
            COUNT(t.ID) AS booked
        FROM Flight f
        JOIN Airplane a
            ON f.airline_name = a.airline_name
        AND f.airplane_id = a.ID
        LEFT JOIN Ticket t
            ON f.airline_name = t.airline_name
        AND f.flight_number = t.flight_number
        AND f.departure_datetime = t.departure_datetime
        WHERE f.airline_name = %s
        AND f.flight_number = %s
        AND f.departure_datetime = %s
        GROUP BY a.num_seats;
        """

        cursor.execute(query, (
            data["airline_name"],
            data["flight_number"],
            data["flight_date"]
        ))
        row = cursor.fetchone()

        if row is None:
            flash("Flight not found.")
        elif row["booked"] >= row["num_seats"]:
            flash("Flight is full.")
        else:
            query = """
            INSERT INTO Ticket (
                customer_email,
                airline_name,
                flight_number,
                departure_datetime,
                card_type,
                card_number,
                name_on_card,
                expiration_date,
                purchase_datetime
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, NOW()
            );
            """
            cursor.execute(query, (
                session["user"],
                data["airline_name"],
                data["flight_number"],
                data["flight_date"],
                data["card_type"],
                data["card_number"],
                data["name_on_card"],
                data["expiration_date"]
            ))
            conn.commit()
        
            flash("Ticket purchased successfully!", "success")
        cursor.close()
        conn.close()
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
        conn = get_connection()
        cursor = conn.cursor()

        # Make sure the customer actually took this past flight before reviewing.
        user_took_the_flight = """
        SELECT 1
        FROM Ticket
        WHERE customer_email = %s
        AND airline_name = %s
        AND flight_number = %s
        AND departure_datetime = %s;
        """
        cursor.execute(user_took_the_flight, (
            session["user"],
            data["airline_name"],
            data["flight_number"],
            data["flight_date"]
        ))

        if cursor.fetchone() is None:
            flash("You cannot rate this flight.")
        else:
            query = """
            INSERT INTO Review(
                customer_email,
                airline_name,
                flight_number,
                departure_datetime,
                rating,
                comment
            )
            VALUES (%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                rating = VALUES(rating),
                comment = VALUES(comment);
            """
            cursor.execute(query, (
                session["user"],
                data["airline_name"],
                data["flight_number"],
                data["flight_date"],
                data["rating"],
                data["comment"]
            ))
            conn.commit()
            flash("Thanks for your feedback!", "success")

        cursor.close()
        conn.close()
        return redirect(url_for("customer_rate"))

    # GET: list flights the customer already took (eligible to rate).
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    pastflight_query = """
    SELECT f.airline_name,
        f.flight_number,
        f.departure_datetime,
        f.departure_airport,
        f.arrival_airport
    FROM Ticket t
    JOIN Flight f
    ON t.airline_name = f.airline_name
    AND t.flight_number = f.flight_number
    AND t.departure_datetime = f.departure_datetime
    WHERE t.customer_email = %s
    AND f.departure_datetime < NOW()
    ORDER BY f.departure_datetime DESC;
    """
    cursor.execute(pastflight_query, (session["user"],))
    past_flights = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("customer/rate.html", past_flights=past_flights)


# ===========================================================================
# Airline Staff use cases
# ===========================================================================
@app.route("/staff")
@role_required("staff")
def staff_home():
    """Staff home — default: future flights for their airline (next 30 days)."""
    flights = []
    # TODO(db): flights for session["user"]'s airline, next 30 days.
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
    flights = []
    customers = []
    selected_flight = None
    # TODO(db): flights for staff's airline filtered by f (default next 30 days).
    # If f["flight_number"] (and date) is set: customers = passengers on it.
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
        # TODO(db): INSERT flight for the staff member's airline.
        flash("Flight created.", "success")
        return redirect(url_for("staff_view_flights"))

    airports, airplanes = [], []
    # TODO(db): airports = all airports; airplanes = planes owned by this airline.
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
        # TODO(db): UPDATE flight status (only for this staff's airline).
        flash("Flight status updated.", "success")
        return redirect(url_for("staff_change_status"))

    flights = []
    # TODO(db): flights = this airline's flights (to populate the dropdown).
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
        # TODO(db): INSERT airplane for the staff member's airline.
        flash("Airplane added.", "success")
        return redirect(url_for("staff_add_airplane"))

    airplanes = []
    # TODO(db): airplanes = all planes owned by this airline (confirmation list).
    return render_template("staff/add_airplane.html", airplanes=airplanes)


@app.route("/staff/ratings")
@role_required("staff")
def staff_ratings():
    """Per-flight average rating + all comments for this airline's flights."""
    ratings = []
    # TODO(db): ratings = [{flight_number, flight_date, avg_rating,
    #                       comments:[{customer, rating, comment}]}, ...]
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
    total_sales = 0
    monthly = []
    # TODO(db): total_sales = SUM/COUNT of tickets in range for this airline.
    #           monthly = month-wise counts (drives the bar chart).
    return render_template(
        "staff/reports.html", f=f, total_sales=total_sales, monthly=monthly,
    )


if __name__ == "__main__":
    app.run(debug=True)
