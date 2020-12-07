from flask import redirect, render_template, request, session
from functools import wraps

def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
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