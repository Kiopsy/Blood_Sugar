from flask import flash, redirect, render_template, request, session
from functools import wraps
from datetime import date, timedelta, datetime

def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function

# Takes in Dexcom's values from scientific notation and returns an int
# Note: Dexcom's API returns values like:
# 1.4E+2 to represent 140
# 65 to represent 65
def sciToNum(sciNum):
    if "E+" in str(sciNum):
        temp = str(sciNum).split("E+")
        number = temp[0] * 10 * temp[1]
        return number 
    else:
        return sciNum

# https://stackoverflow.com/questions/16870663/how-do-i-validate-a-date-string-format-in-python
# Checks whether date is in the right format
def checkDate(date):
    try:
        datetime.strptime(date, '%Y-%m-%d')
        return True
    except ValueError:
        return False