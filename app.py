import os
from datetime import date, timedelta, datetime
from flask import Flask, flash, redirect, render_template, request, session
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import sciToNum, login_required, checkDate


import sqlite3
import http.client
import json

app = Flask(__name__)

# Clears cache

@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r

app.config.update(
    TESTING=True,
    SECRET_KEY=b'pk_aafb84848ef145/#2sa'
)

CLIENT_ID = "F96Uu0m1gIR85MYFWEu25yl2ul3Tjjeo"
CLIENT_SECRET = "5qQ7qVnZRRFTNM99"
REDIRECT_URI = "http://127.0.0.1:5000/dexcom"

access_token = ""
authorization_code = ""

glucose_data = []
event_data = []
start_date = ""
end_date = ""

@app.route("/dates",  methods=["GET", "POST"])
@login_required
def dates():
    if request.method == "POST":
        global start_date, end_date, start_datetime, end_datetime

        # Ensure dates are in date format
        if not checkDate(request.form.get("trip-start")) or not checkDate(request.form.get("trip-end")):
            flash("Must input the date format: YYYY-MM-DD")
            return render_template("dates.html")

        # Ensure start date was submitted
        if not request.form.get("trip-start"):
            flash("Must provide start date!")
            return render_template("dates.html")

        # Ensure password was submitted
        elif not request.form.get("trip-end"):
            flash("Must provide end date!")
            return render_template("dates.html")
        
        start_date = request.form.get("trip-start")
        end_date = request.form.get("trip-end")

        start = start_date.split("-")
        end = end_date.split("-")

        
        # Dexcom only has up to 3 months of data so we need to ensure input dates comes after that

        # https://www.kite.com/python/answers/how-to-get-a-date-six-months-from-today-using-datetime-in-python
        # This finds the date 3 months before the current date
        today = datetime.now()
        min_day = today.day
        min_month = (today.month - 3) % 12
        min_year = today.year + ((today.month - 3) // 12)

        min = str(datetime(min_year, min_month, min_day)).split(" ")[0].split("-")

        start_datetime = date(int(start[0]), int(start[1]), int(start[2])) 
        end_datetime = date(int(end[0]), int(end[1]), int(end[2]))
        min_datetime = date(int(min[0]), int(min[1]), int(min[2])) 

        # Ensure start date comes before end date
        if end_datetime < start_datetime:
            flash("Start date must be before end date!")
            return render_template("dates.html")

        # Ensure start date and end date are after the 3 month minimum date for Dexcom
        if end_datetime < min_datetime or start_datetime < min_datetime:
            flash(f"Start date and end date must come after {min_datetime}!")
            return render_template("dates.html")
    
        start_date = start_date + "T00:00:00"
        end_date = end_date + "T00:00:00"

        # Redirect the user API route
        return redirect("/API")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("dates.html")

@app.route("/graph")
@login_required
def graph():
    global start_datetime, end_datetime

    # Connects to database
    connection = sqlite3.connect("database.db") 
  
    # SQL Cursor
    cursor = connection.cursor()

    # Calculates the amount of days between start date and end date
    delta_days = end_datetime - start_datetime

    id = session["user_id"]

    temp_day = start_datetime
    
    # Data will be populated will all of Dexcom's returned data between start and end date
    data = []

    # Iterates through amount of days between start date and end date
    for i in range(delta_days.days):
        # Selects values within glucose, carbs, and insulin for each day betwen start and end date
        cursor.execute(f"SELECT value, timestamp FROM glucose WHERE id IN(SELECT id FROM users WHERE id = {id}) AND timestamp LIKE '{temp_day}%'")
        glucose = cursor.fetchall()
        cursor.execute(f"SELECT value, timestamp FROM carbs WHERE id IN(SELECT id FROM users WHERE id = {id}) AND timestamp LIKE '{temp_day}%'")
        carbs = cursor.fetchall()
        cursor.execute(f"SELECT value, timestamp FROM insulin WHERE id IN(SELECT id FROM users WHERE id = {id}) AND timestamp LIKE '{temp_day}%'")
        insulin = cursor.fetchall()

        dayList = [glucose, carbs, insulin]
        
        # dayDict consists of a dictionary with key of the current date and a list of 3 tuples: glucose, carb, and insulin data for that day. 
        dayDict = {str(temp_day):dayList} 
        
        # data will be a list of these dictionaries
        data.append(dayDict)

        # Increments to next day
        temp_day += timedelta(days=1)

    return render_template("graph.html", data=json.dumps(data), days=int(delta_days.days))

@app.route("/about",  methods=["GET"])
@login_required
def about():
    # Renders the about page
    return render_template("about.html")

@app.route("/account",  methods=["GET", "POST"])
@login_required
def account():
    # Connects to database
    connection = sqlite3.connect("database.db") 
  
    # SQL Cursor
    cursor = connection.cursor()

    # Selects the account data for current user
    sql_command = "SELECT * FROM users WHERE id=?"
    cursor.execute(sql_command, [session["user_id"]])
    rows = cursor.fetchall()
    connection.close()

    # Renders the account page with passed in user account data
    return render_template("account.html", details=rows[0])

@app.route("/accountdetails",  methods=["GET", "POST"])
@login_required
def account_details():
    # The four options for labels a user can select to display on their account
    labels = ["Type-1 Diabetic", "Caregiver", "Clinical Usage", "Other"]

    if request.method == "POST":

        # Ensures the user inputted all values within the form (full name, label, and description)
        if not request.form.get("fullname") or not request.form.get("label") or not request.form.get("description") :
            flash("Must input all three values!")
            return render_template("accountdetails.html", labels=labels)

        # Ensures the submitted label is one of the four options given
        if not request.form.get("label") in labels:
            flash("Must choose a label from the presented options!")
            return render_template("accountdetails.html", labels=labels)

        # Connects to database
        connection = sqlite3.connect("database.db") 
  
        # SQL Cursor
        cursor = connection.cursor()

        # Updates the account details on the current user's account
        sql_command = "UPDATE users SET fullname=?, label=?, description=? WHERE id=?"
        cursor.execute(sql_command, [request.form.get("fullname"), request.form.get("label"), request.form.get("description"), session["user_id"]])

        # Pushes changes to database
        connection.commit()

        # Selects account data from current user
        sql_command = "SELECT * FROM users WHERE id=?"
        cursor.execute(sql_command, [session["user_id"]])
        rows = cursor.fetchall()

        connection.close()

        # Displays to user that they have registered successfully
        flash("Account Details Set!")

        # Renders the account page with passed in user account data
        return render_template("account.html", details=rows[0])

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("accountdetails.html", labels=labels)


@app.route("/changepassword",  methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":

        # Ensures all password input was submitted
        if not request.form.get("current") or not request.form.get("password") or not request.form.get("confirmation"):
            flash("Must input all three passwords!")
            return render_template("changepass.html")
        
        # Connects to database
        connection = sqlite3.connect("database.db") 
  
        # SQL Cursor
        cursor = connection.cursor()

        # Query database for username
        cursor.execute("SELECT * FROM users WHERE id = ?", [session["user_id"]])
        rows = cursor.fetchall()

        # Ensures current password is correct
        if not check_password_hash(rows[0][2], request.form.get("current")):
            flash("Invalid current password!")
            return render_template("changepass.html")

        # Hashes the password
        hash = generate_password_hash(request.form.get("password"))

        # Updates database with new password for the user
        sql_command = "UPDATE users SET hash=? WHERE id=?"
        cursor.execute(sql_command, [hash, session["user_id"]])

        # Pushes changes to database
        connection.commit()
        connection.close()

        return redirect("/account")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("changepass.html")

# Note: Dexcom is a company that produces CGMs (Continuous Glucose Monitor) for type-1 diabetics and their blood sugars.
@app.route("/API",  methods=["GET"])
@login_required
def API():
    # Redirects user to Dexcom's login for API
    # Note: after logging in, user is redirected to dexcom route
    return redirect(f"https://api.dexcom.com/v2/oauth2/login?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=offline_access")

@app.route("/dexcom",  methods=["GET", "POST"])
@login_required
def dexcom():
    # Authenticates and authorizes to retrieve data from Dexcom

    # Retrieves authorization code from Dexcom API
    authorization_code = request.args.get("code")

    # Retrieves access token from Dexcom API
    conn = http.client.HTTPSConnection("api.dexcom.com")

    payload = f"client_secret={CLIENT_SECRET}&client_id={CLIENT_ID}&code={authorization_code}&grant_type=authorization_code&redirect_uri={REDIRECT_URI}"
    headers = {
        'content-type': "application/x-www-form-urlencoded",
        'cache-control': "no-cache"
    }

    conn.request("POST", "https://api.dexcom.com/v2/oauth2/token", payload, headers)
    res = conn.getresponse()
    data = res.read()
    data = data.decode("utf-8")
    access_token = json.loads(data)["access_token"]

    # Using the access token, retrieve the bearer token
    # Make requests using the bearer token
    headers = {
        'authorization': f"Bearer {access_token}"
    }

    global glucose_data, event_data
    
    # Requests EGVs from Dexcom
    # EGVs are glucose values
    conn.request("GET", f"https://api.dexcom.com/v2/users/self/egvs?startDate={start_date}&endDate={end_date}", headers=headers)

    res = conn.getresponse()
    data = res.read()
    data = data.decode("utf-8")

    # Creates a list of glucose values
    glucose_data = json.loads(data)["egvs"]
    glucose_data.reverse()

    # Request Events from Dexcom
    # Events can consist of carb values and insulin values
    conn.request("GET", f"https://api.dexcom.com/v2/users/self/events?startDate={start_date}&endDate={end_date}", headers=headers)

    res = conn.getresponse()
    data = res.read()
    data = data.decode("utf-8")

    event_data = json.loads(data)["events"]
    event_data.reverse()

    # Connects to database
    connection = sqlite3.connect("database.db") 
  
    # SQL Cursor
    cursor = connection.cursor()

    # Deletes all previous data from the table
    cursor.execute("DELETE FROM glucose")
    cursor.execute("DELETE FROM carbs")
    cursor.execute("DELETE FROM insulin")

    # Iterates through all glucose values
    for glucose in glucose_data:
        
        # SQL command to insert glucose data into glucose table
        sql_command = "INSERT INTO glucose VALUES (?, ?, ?)"
        cursor.execute(sql_command, [session["user_id"], glucose["value"], glucose["systemTime"].replace("T", " ")])

    # Iterates through all events
    for event in event_data:

        # Determines whether current event is a carbs or insulin event 
        if event["eventType"] == "carbs":
            
            # SQL command to insert carbs data into carbs table
            sql_command = "INSERT INTO carbs VALUES (?, ?, ?)"
            cursor.execute(sql_command, [session["user_id"], int(sciToNum(event["value"])), event["systemTime"].replace("T", " ")])

        elif event["eventType"] == "insulin":
            

            # SQL command to insert insulin data into insulin table 
            sql_command = "INSERT INTO insulin VALUES (?, ?, ?)"
            cursor.execute(sql_command, [session["user_id"], sciToNum(event["value"]), event["systemTime"].replace("T", " ")])

    # Commits SQL changes
    connection.commit()
    connection.close()

    # Redirects user to graph route
    return redirect("/graph")

@app.route("/",  methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide username!")
            return render_template("login.html")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password!")
            return render_template("login.html")
        
        # Connects to database
        connection = sqlite3.connect("database.db") 
  
        # SQL Cursor
        cursor = connection.cursor()

        # Query database for username
        cursor.execute("SELECT * FROM users WHERE username = ?", [request.form.get("username")])
        rows = cursor.fetchall()

        # Ensure username exists and password is correct
        if not rows or not check_password_hash(rows[0][2], request.form.get("password")):
            flash("Invalid username and/or password!")
            return render_template("login.html")

        # Remember which user has logged in
        session["user_id"] = rows[0][0]

        connection.close()

        # Redirect user to about page
        return redirect("/account")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/register",  methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide username!")
            return render_template("register.html")

        # Ensure password was submitted
        elif not request.form.get("password") or not request.form.get("confirmation"):
            flash("Must provide username!")
            return render_template("register.html")

        # Ensure password and password confirmation are equal
        elif request.form.get("password") != request.form.get("confirmation"):
            flash("Passwords do not match!")
            return render_template("register.html")

        username = request.form.get("username")

        # Hashes the password
        hash = generate_password_hash(request.form.get("password"))

        # Connects to database
        connection = sqlite3.connect("database.db") 
  
        # SQL Cursor
        cursor = connection.cursor()

        # Query database to see if username already exists
        cursor.execute("SELECT * FROM users WHERE username = ?", [request.form.get("username")])
        rows = cursor.fetchall()

        # Ensures that username does not already exist
        if rows:
            flash("Username is taken!")
            return render_template("register.html")
        
        # Inserts a new user into the SQL database
        cursor.execute("INSERT INTO users (username, hash) VALUES(?, ?)", [username, hash])

        # Selects the newly created user from the SQL database and remembers they have logged in
        cursor.execute("SELECT id FROM users WHERE username = ?", [request.form.get("username")])
        rows = cursor.fetchall()
        session["user_id"] = rows[0][0]
        
        connection.commit()
        connection.close()

        # Redirect user to about page
        return redirect("/accountdetails")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

