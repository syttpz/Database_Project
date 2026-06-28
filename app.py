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

    #one way, round trip
    results, return_results = [], []
    if searched:
        pass

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
        WHERE (dep.city = %s OR dep.name = %s)
            AND (arr.city = %s OR arr.name = %s)
            AND DATE(f.departure_datetime) = %s
        """

        cursor.execute(query, (
            f["source"], f["source"],
            f["destination"], f["destination"],
            f["depart_date"]
        ))

        results = cursor.fetchall()

        if f["trip_type"] == "round":
            # swapped destination and source
            cursor.execute(query, (
                f["destination"], f["destination"],
                f["source"], f["source"],
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
        conn = get_connection()
        cursor = conn.cursor()

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
    """View My Flights — default = future flights; optional filters."""
    f = {
        "scope": request.args.get("scope", "future"),
        "source": request.args.get("source", ""),
        "destination": request.args.get("destination", ""),
        "start_date": request.args.get("start_date", ""),
        "end_date": request.args.get("end_date", ""),
    }
    flights = []
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
        # Card expiry comes in as MM/YY (e.g. 07/29). The Ticket.expiration_date
        # column is DATE, so normalize to the first day of that month:
        # 07/29 -> 2029-07-01.
        exp = data["expiration_date"].strip()
        try:
            mm, yy = exp.split("/")
            data["expiration_date"] = f"20{int(yy):02d}-{int(mm):02d}-01"
        except (ValueError, IndexError):
            flash("Invalid expiration date. Use MM/YY (e.g. 07/29).")
            return redirect(url_for("customer_purchase",
                                    airline_name=data["airline_name"],
                                    flight_number=data["flight_number"],
                                    flight_date=data["flight_date"]))

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
