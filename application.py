import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

currentPrices = []

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Stocks will return a dictionary with the keys 'name', 'symbol', and 'shares'
    stocks = db.execute("SELECT name, symbol, SUM(shares) AS shares FROM stock WHERE id = :user_id GROUP BY name, symbol ORDER BY name", user_id=session["user_id"])
    totalShareValue = 0
    for i in range(len(stocks)):
        # Use the lookup function to find the current price of the stock
        symbol = stocks[i]['symbol']
        quote = lookup(symbol)
        currentprice = quote['price']
        # Add a new key-value pair to the stock dictionary with key 'currentprice'
        stocks[i]['currentprice'] = currentprice
        stocks[i]['total'] = currentprice * (stocks[i]['shares'])
        totalShareValue = totalShareValue + stocks[i]['total']

    cash = db.execute("SELECT cash AS FLOAT FROM users WHERE id = :user_id", user_id=session["user_id"])

    return render_template("index.html", stocks = stocks, cash = cash[0]['FLOAT'], totalShareValue = totalShareValue)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol")

        # Ensure share number was submitted
        elif not request.form.get("shares"):
            return apology("must provide shares")

        # Use helper.py lookup function to access data
        data = lookup(request.form.get("symbol"))

        # Deal with invalid symbol
        if data == None:
            return apology("invalid symbol")

        # Record the time and date of the transaction
        now = datetime.datetime.now()

        # Query database for user with user_id in users table and check cash balance against price of shares
        cash = db.execute("SELECT cash AS FLOAT FROM users WHERE id = :user_id", user_id=session["user_id"])
        cash = cash[0]['FLOAT']
        price = data["price"]
        shares = int(request.form.get("shares"))
        if cash >= (price * shares):
            # Query database for user with user_id in users table and update cash after sale
            db.execute("UPDATE users SET cash = cash - (:shares * :price) WHERE id = :user_id", user_id=session["user_id"], price=float(data["price"]), shares=request.form.get("shares"))

            # Add share data to stocks table
            db.execute("INSERT INTO stock (id, symbol, name, shares, price, transacted) VALUES (:user_id, :symbol, :name, :shares, :price, :transacted)", user_id=session["user_id"], symbol=data["symbol"], name=data["name"], shares=request.form.get("shares"), price=data["price"], transacted=now.strftime('%Y-%m-%d %H:%M:%S'))

            # Redirect user to index
            flash("Bought!")
            return redirect("/")

        # Deal with insufficient funds
        else:
            return apology("insufficient funds")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # stocks will return a dictionary with the keys 'name', 'symbol', and 'shares'
    stocks = db.execute("SELECT symbol, shares, price, transacted FROM stock WHERE id = :user_id ORDER BY transacted", user_id=session["user_id"])

    return render_template("history.html", stocks = stocks)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure stock name was submitted
        if not request.form.get("symbol"):
            return apology("must enter a symbol")

        # Use helper.py lookup function to access data
        quote = lookup(request.form.get("symbol"))

        # Deal with invalid symbol
        if quote == None:
            return apology("invalid symbol")

        return render_template("quoted.html", name = quote["name"], symbol = quote["symbol"], price = usd(quote["price"]))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure password was confirmed
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 403)

        # Ensure password and confirmation match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 403)

        # Ensure username does not already exist in the database
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if len(rows) == 1:
            return apology("username already exists", 403)

        # Insert username and encrypted password into database
        db.execute("INSERT INTO users (username, hash) VALUES(:username, :password)", username=request.form.get("username"), password=generate_password_hash((request.form.get("password"))))

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was selected
        if not request.form.get("symbol"):
            return apology("must select symbol", 403)

        # Ensure number of shares was entered
        elif not request.form.get("shares"):
            return apology("must enter number of shares", 403)

        # Check if user has enough shares of selected stock
        shares = db.execute("SELECT SUM(shares) AS shares FROM stock WHERE id = :user_id AND symbol = :symbol", user_id=session["user_id"], symbol=request.form.get("symbol"))

        if shares[0]['shares'] < int(request.form.get("shares")):
            return apology("insufficient shares", 403)

        # Record the time and date of the transaction
        now = datetime.datetime.now()

        # Use helper.py lookup function to access data
        data = lookup(request.form.get("symbol"))

        # Query database for user with user_id in users table and update cash after sale
        db.execute("UPDATE users SET cash = cash + (:shares * :price) WHERE id = :user_id", user_id=session["user_id"], price=float(data["price"]), shares=request.form.get("shares"))

        # Query database for user with user_id in stock table and add sale transaction
        db.execute("INSERT INTO stock (id, symbol, name, shares, price, transacted) VALUES (:user_id, :symbol, :name, :shares, :price, :transacted)"
        , user_id=session["user_id"], symbol=data["symbol"], name=data["name"], shares=-1*int(request.form.get("shares")), price=data["price"], transacted=now.strftime('%Y-%m-%d %H:%M:%S'))

        # Redirect user to index
        flash("Sold!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        # Populate select menu with symbols from user's portfolio of stocks
        symbols = db.execute("SELECT DISTINCT symbol FROM stock WHERE id = :user_id", user_id=session["user_id"])

        return render_template("sell.html", symbols = symbols)

@app.route("/credit", methods=["GET", "POST"])
@login_required
def credit():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure credit amount was entered
        if not request.form.get("credit"):
            return apology("must enter credit amount", 403)

        # Ensure credit amount greater than 0 was entered
        if int(request.form.get("credit")) == 0:
            return apology("must enter amount greater than 0 to credit your account", 403)

        # Query database for user with user_id in users table and update cash after account credit
        db.execute("UPDATE users SET cash = cash + :credit WHERE id = :user_id", user_id=session["user_id"], credit=request.form.get("credit"))

        # Redirect user to index
        flash("Account credited!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("credit.html")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
