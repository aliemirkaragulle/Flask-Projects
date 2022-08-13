import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]

    user_transactions = db.execute(
        "SELECT symbol, SUM(shares) AS shares, price FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
    user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    user_cash = user_cash_db[0]["cash"]

    return render_template("index.html", user_transactions=user_transactions, cash=user_cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Invalid Amount")

        if not symbol:
            return apology("You Must Provide a Symbol")

        stock = lookup(symbol.upper())

        if stock is None:
            return apology("Invalid Quote")

        if shares < 0:
            return apology("Invalid Transaction")

        db.execute("CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, symbol TEXT, shares INTEGER, price REAL, date DATETIME DEFAULT CURRENT_TIMESTAMP);")

        user_id = session["user_id"]
        user_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)

        user_cash = user_db[0]["cash"]
        stock_cost = shares * stock["price"]

        if user_cash < stock_cost:
            return apology("Insufficient Funds")

        new_user_cash = user_cash - stock_cost
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_user_cash, user_id)

        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES(?, ?, ?, ?)",
                   user_id, stock["symbol"], shares, stock["price"])

        flash("Bought!")

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    transactions_db = db.execute("SELECT * FROM transactions WHERE user_id = ?", user_id)

    return render_template("history.html", transactions=transactions_db)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
    if request.method == "POST":
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("You Must Provide a Symbol")

        stock = lookup(symbol.upper())

        if stock is None:
            return apology("Invalid Quote")

        return render_template("quoted.html", name=stock["name"], price=stock["price"], symbol=stock["symbol"])

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("You Must Provide a Username")

        if not password:
            return apology("You Must Provide a Password")

        if not confirmation:
            return apology("You Must Provide a Confirmation")

        if password != confirmation:
            return apology("Passwords Do Not Match")

        password_hash = generate_password_hash(password)

        try:
            user = db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, password_hash)
        except:
            return apology("Username Already Exists")

        session["user_id"] = user

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        if not symbol:
            return apology("You Must Provide a Symbol")

        stock = lookup(symbol.upper())

        if stock is None:
            return apology("Invalid Quote")

        if shares < 0:
            return apology("Invalid Transaction")

        db.execute("CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, symbol TEXT, shares INTEGER, price REAL, date DATETIME DEFAULT CURRENT_TIMESTAMP);")

        user_id = session["user_id"]
        user_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)

        user_cash = user_db[0]["cash"]
        stock_cost = shares * stock["price"]

        user_shares = db.execute(
            "SELECT shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id, symbol)
        user_shares_acc = user_shares[0]["shares"]

        if shares > user_shares_acc:
            return apology("Invalid Transaction")

        new_user_cash = user_cash + stock_cost

        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_user_cash, user_id)

        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES(?, ?, ?, ?)",
                   user_id, stock["symbol"], (-1) * shares, stock["price"])

        flash("Sold!")

        return redirect("/")

    else:
        user_id = session["user_id"]
        user_symbols = db.execute(
            "SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", user_id)

        return render_template("sell.html", symbols=[row["symbol"] for row in user_symbols])


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Add additional cash to the account"""
    if request.method == "POST":
        deposit_amount = int(request.form.get("deposit_amount"))

        if not deposit_amount:
            return apology("Enter a Valid Amount")

        user_id = session["user_id"]
        user_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)

        user_cash = user_db[0]["cash"]
        new_user_cash = user_cash + deposit_amount

        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_user_cash, user_id)

        return redirect("/")

    else:
        return render_template("deposit.html")