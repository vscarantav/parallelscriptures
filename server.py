# server.py
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, session, g
import os
import re
import time
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import smtplib, ssl


# ----------------------------
# Canonical books & chapters
# ----------------------------
BOOK_SLUGS = [
    "1-ne", "2-ne", "jacob", "enos", "jarom", "omni",
    "w-of-m", "mosiah", "alma", "hel", "3-ne", "4-ne", "morm", "ether", "moro",
]

BOOK_CHAPTERS = {
    "1-ne": 22, "2-ne": 33, "jacob": 7, "enos": 1, "jarom": 1, "omni": 1,
    "w-of-m": 1, "mosiah": 29, "alma": 63, "hel": 16, "3-ne": 30, "4-ne": 1,
    "morm": 9, "ether": 15, "moro": 10,
}


# ----------------------------
# Load precomputed localized names
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOOKSNAMES_PATH = os.path.join(BASE_DIR, "booksnames.json")

try:
    with open(BOOKSNAMES_PATH, "r", encoding="utf-8") as f:
        BOOKS_NAMES = json.load(f)   # { "<lang>": { "<slug>": "<Localized Title>", ... }, ... }
except Exception:
    BOOKS_NAMES = {}                 # graceful if file missing/corrupt


# ----------------------------
# /api/books — now served from booksnames.json (with fallback)
# ----------------------------
_BOOKS_CACHE = {}   # { lang: { "at": epoch_seconds, "data": [...] } }
_CACHE_TTL   = 60 * 60 * 24  # 24h

def _get_books_for_lang(lang: str):
    now = time.time()
    hit = _BOOKS_CACHE.get(lang)
    if hit and (now - hit["at"] < _CACHE_TTL):
        return hit["data"]

    out = []

    # 1. Try to load authoritative names from the downloaded JSON file first
    file_data = _load_book_data(lang)
    if file_data:
        for slug in BOOK_SLUGS:
            # Safe get in case a book is missing from the file
            book_meta = file_data.get(slug, {}).get("meta", {})
            localized_name = book_meta.get("name", slug.replace("-", " ").title())
            
            out.append({
                "abbr": slug,
                "name": localized_name,
                "chapters": BOOK_CHAPTERS.get(slug, 0),
            })
    else:
       # 2. Fallback to booksnames.json or raw slugs
       names = BOOKS_NAMES.get(lang, {}) 
       for slug in BOOK_SLUGS:
           out.append({
               "abbr": slug,
               "name": names.get(slug, slug.replace("-", " ").title()),
               "chapters": BOOK_CHAPTERS[slug],
            })
    _BOOKS_CACHE[lang] = {"at": now, "data": out}
    return out
# ----------------------------
# Local File Loader
# ----------------------------
_FILE_CACHE = {}
 
def _load_book_data(lang: str):
    """Loads the entire JSON content for a language from all_books/{lang}.json"""
    # 1. Check cache first
    if lang in _FILE_CACHE:
        return _FILE_CACHE[lang]

    # 2. Sanitize input to prevent directory traversal
    clean_lang = re.sub(r'[^a-zA-Z0-9-]', '', lang)
    file_path = os.path.join(BASE_DIR, "all_books", f"{clean_lang}.json")
    
    # 3. Read file if exists
    if not os.path.exists(file_path):
        return None
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            _FILE_CACHE[lang] = data
            return data
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

# ----------------------------
# Flask app & routes
# ----------------------------
app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')

# cache static files in browser for 1 day
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")  # replace in prod
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///users.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config.setdefault("SECURITY_TOKEN_MAX_AGE", 3600)  # 1 hour for verify/reset links
app.config.setdefault("SMTP_HOST", os.environ.get("SMTP_HOST", ""))
app.config.setdefault("SMTP_PORT", int(os.environ.get("SMTP_PORT", "587")))
app.config.setdefault("SMTP_USER", os.environ.get("SMTP_USER", ""))
app.config.setdefault("SMTP_PASS", os.environ.get("SMTP_PASS", ""))
app.config.setdefault("SMTP_SENDER", os.environ.get("SMTP_SENDER", "no-reply@example.com"))
# If emails aren't configured, optionally show dev links on pages (never enable in prod)
app.config.setdefault("SHOW_DEV_LINKS", os.environ.get("SHOW_DEV_LINKS", "1" if not os.environ.get("SMTP_HOST") else "0") in ("1","true","True"))
app.config.setdefault("SMTP_USE_SSL", os.environ.get("SMTP_USE_SSL", "0") in ("1","true","True"))

# --- DB & User model ---
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    email_verified_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw, method="pbkdf2:sha256", salt_length=16)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

# Ensure tables exist (safe if already created)
with app.app_context():
    db.create_all()
    # --- lightweight SQLite migration (SQLAlchemy 2.x safe) ---
    try:
        # Use SQLAlchemy 2.0 execution API
        with db.engine.begin() as conn:
            rows = conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
            cols = {row[1] for row in rows}  # row[1] is the column name
            if "email_verified_at" not in cols:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN email_verified_at DATETIME NULL")
    except Exception as e:
        app.logger.warning("Startup migration skipped/failed: %s", e)


# --- token + mail helpers ---
def _serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="acct")

def _sign(payload: dict) -> str:
    return _serializer().dumps(payload)

def _unsign(token: str, max_age: int):
    return _serializer().loads(token, max_age=max_age)

def _send_email(to_addr: str, subject: str, body: str) -> bool:
    host = app.config["SMTP_HOST"]
    user = app.config["SMTP_USER"]
    pw   = app.config["SMTP_PASS"]
    sender = app.config["SMTP_SENDER"]
    port = app.config["SMTP_PORT"]
    debug = os.environ.get("SMTP_DEBUG", "") in ("1","true","True")
    msg = f"From: {sender}\r\nTo: {to_addr}\r\nSubject: {subject}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}"
    if not host or not user or not pw:
        # Dev fallback: print the email content to logs
        app.logger.warning("SMTP not configured; would send email to %s:\n%s", to_addr, msg)
        return False
    ctx = ssl.create_default_context()
    try:
        # Use implicit SSL if requested or on port 465; otherwise STARTTLS.
        if app.config["SMTP_USE_SSL"] or port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx) as s:
                if debug: s.set_debuglevel(1)
                s.login(user, pw)
                s.sendmail(sender, [to_addr], msg.encode("utf-8"))
        else:
            with smtplib.SMTP(host, port) as s:
                if debug: s.set_debuglevel(1)
                s.starttls(context=ctx)
                s.login(user, pw)
                s.sendmail(sender, [to_addr], msg.encode("utf-8"))
        return True
    except Exception as e:
        app.logger.error("SMTP send failed: %s", e)
        return False

    
# Build absolute URLs for email links
def _abs_url(endpoint, **params):
    # Works behind proxies like Render/Heroku when X-Forwarded headers are set
    # If not, falls back to http://localhost
    try:
        base = request.url_root.rstrip("/")
    except RuntimeError:
        base = ""
    return base + url_for(endpoint, **params)

# --- session helpers ---
def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            # Preserve 'next' so we can bounce back after login
            next_url = request.full_path if request.query_string else request.path
            return redirect(url_for("login", next=next_url))
        return fn(*args, **kwargs)
    return wrapper

@app.before_request
def load_current_user():
    uid = session.get("user_id")
    # SQLAlchemy 2.x: use Session.get instead of Query.get
    g.user = db.session.get(User, uid) if uid else None

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.route('/api/books')
def api_books():
    lang = request.args.get('lang', 'por').lower().strip()
    try:
        data = _get_books_for_lang(lang)
        return jsonify({"lang": lang, "books": data})
    except Exception as e:
        return jsonify({"error": f"Failed to load books for {lang}: {e}"}), 500

@app.route('/')
def root():
    return app.send_static_file('index.html')

@app.route('/<path:path>')
def static_proxy(path):
    return send_from_directory(BASE_DIR, path)

# ----------------------------
# Auth routes (Flask sessions)
# ----------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")
    # POST
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    if not email or not password or len(password) < 8:
        return render_template("signup.html", error="Please provide a valid email and a password (min 8 chars)."), 400
    if User.query.filter_by(email=email).first():
        return render_template("signup.html", error="Email is already registered."), 400
    u = User(email=email)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    session["user_id"] = u.id
    # Send verification email (do not return before this block)
    token = _sign({"uid": u.id, "op": "verify"})
    link  = _abs_url("verify_email", token=token)
    sent = _send_email(
        to_addr=u.email,
        subject="Verify your email",
        body=f"Welcome!\n\nConfirm your email by visiting:\n{link}\n\nThis link expires in {app.config['SECURITY_TOKEN_MAX_AGE']//60} minutes."
    )
    # Show verification notice page after signup
    return render_template(
        "verify_notice.html",
        email=u.email,
        dev_link=(link if (not sent and app.config["SHOW_DEV_LINKS"]) else None)
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    # POST
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    u = User.query.filter_by(email=email).first()
    if not u or not u.check_password(password):
        return render_template("login.html", error="Invalid email or password."), 401
    if not u.email_verified_at:
        # Provide a quick re-send link
        resend_url = url_for("resend_verification", email=email)
        return render_template("login.html", error=f"Email not verified. Please check your inbox or  {resend_url}"), 403

    session["user_id"] = u.id
    nxt = request.args.get("next") or url_for("root")
    return redirect(nxt)

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("root"))

# ---------- Email verification ----------
@app.get("/verify")
def verify_email():
    token = request.args.get("token", "")
    try:
        data = _unsign(token, max_age=app.config["SECURITY_TOKEN_MAX_AGE"])
        if data.get("op") != "verify":
            raise BadSignature("wrong op")
        uid = int(data["uid"])
    except (BadSignature, SignatureExpired, KeyError, ValueError) as e:
        return render_template("verify_notice.html", error="Invalid or expired verification link."), 400
    u = User.query.get(uid)
    if not u:
        return render_template("verify_notice.html", error="Account not found."), 404
    if not u.email_verified_at:
        u.email_verified_at = datetime.utcnow()
        db.session.commit()
    session["user_id"] = u.id
    return render_template("verify_notice.html", success="Email verified!")

@app.get("/verify/resend")
def resend_verification():
    # If email provided as query param, prefer it; else use current session
    email = (request.args.get("email") or (g.user.email if getattr(g, "user", None) else "")).strip().lower()
    if not email:
        return render_template("verify_notice.html", error="No email provided."), 400
    u = User.query.filter_by(email=email).first()
    if not u:
        return render_template("verify_notice.html", error="Account not found."), 404
    if u.email_verified_at:
        return render_template("verify_notice.html", success="Email already verified.")
    token = _sign({"uid": u.id, "op": "verify"})
    link  = _abs_url("verify_email", token=token)
    sent = _send_email(u.email, "Verify your email", f"Verify your email:\n{link}\n\nThis link expires in {app.config['SECURITY_TOKEN_MAX_AGE']//60} minutes.")
    return render_template(
        "verify_notice.html",
        success=f"Verification link sent to {u.email}.",
        dev_link=(link if (not sent and app.config["SHOW_DEV_LINKS"]) else None)
    )
# ---------- Password reset ----------
@app.route("/password/forgot", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot.html")
    email = (request.form.get("email") or "").strip().lower()
    # Response is generic to avoid account enumeration
    info_msg = "If that email exists, we sent a reset link."
    if not email:
        return render_template("forgot.html", info=info_msg)
    u = User.query.filter_by(email=email).first()
    if u:
        token = _sign({"uid": u.id, "op": "reset"})
        link  = _abs_url("reset_password", token=token)
        sent = _send_email(u.email, "Reset your password", f"Reset your password using this link:\n{link}\n\nThis link expires in {app.config['SECURITY_TOKEN_MAX_AGE']//60} minutes.")
        return render_template("forgot.html", info=info_msg, dev_link=(link if (not sent and app.config["SHOW_DEV_LINKS"]) else None))
    return render_template("forgot.html", info=info_msg)

@app.route("/password/reset", methods=["GET", "POST"])
def reset_password():
    token = request.args.get("token", "") if request.method == "GET" else request.form.get("token", "")
    if request.method == "GET":
        return render_template("reset.html", token=token)
    # POST
    new_pw = request.form.get("password") or ""
    if len(new_pw) < 8:
        return render_template("reset.html", token=token, error="Password must be at least 8 characters."), 400
    try:
        data = _unsign(token, max_age=app.config["SECURITY_TOKEN_MAX_AGE"])
        if data.get("op") != "reset":
            raise BadSignature("wrong op")
        uid = int(data["uid"])
    except (BadSignature, SignatureExpired, KeyError, ValueError):
        return render_template("reset.html", error="Invalid or expired reset link."), 400
    u = User.query.get(uid)
    if not u:
        return render_template("reset.html", error="Account not found."), 404
    u.set_password(new_pw)
    db.session.commit()
    session["user_id"] = u.id
    return redirect(url_for("root"))


@app.get("/api/me")
def api_me():
    """Small helper for the frontend to know auth state."""
    if not g.user:
        return jsonify({"authenticated": False})
    return jsonify({
        "authenticated": True,
        "email": g.user.email,
        "created_at": g.user.created_at.isoformat(),
        "email_verified": bool(g.user.email_verified_at),
    })


# Example of protecting an endpoint (uncomment if you add a private page)
# @app.get("/account")
# @login_required
# def account():
#     return jsonify({"email": g.user.email, "created_at": g.user.created_at.isoformat()})


@app.route('/api/chapter')
def api_chapter():
    #Fetches verses for a given book + chapter + lang from local JSON files.
    book = request.args.get('book')
    chapter = request.args.get('chapter')
    lang = request.args.get('lang', 'por')

    if not book or not chapter:
        return jsonify({"error": "Missing 'book' or 'chapter' parameter"}), 400

    # 1. Load data from local file
    data = _load_book_data(lang)
    if not data:
        return jsonify({"error": f"Language '{lang}' not found"}), 404

    # 2. Access the specific book and chapter
    # Structure assumption: data[slug]["chapters"][chapter_number]
    try:
        book_data = data.get(book)
        if not book_data:
             return jsonify({"error": "Book not found", "verses": []}), 404
             
        # Access the "chapters" key first
        chapters_data = book_data.get("chapters", {})
        chapter_content = chapters_data.get(str(chapter))
       
        if not chapter_content:
             return jsonify({"error": "Chapter not found", "verses": []}), 404
             
        # 3. Convert dictionary verses to a sorted list
        # The JSON looks like: { "intro": "...", "1": "And it came...", "2": "..." }
        verses_list = []
        
        for key, text in chapter_content.items():
            if key == "intro":
                continue # Skip intro here, handled in api/intro
            
            # Create a verse object
            verses_list.append({
                "verse": key,
                "text": text
            })
            
        # Sort by verse number (convert string "10" to int 10 for correct sorting)
        verses_list.sort(key=lambda x: int(x["verse"]) if x["verse"].isdigit() else 0)
            
        return jsonify({
            "verses": verses_list,
            "book": book,
            "chapter": chapter,
            "lang": lang
        })
    except Exception as e:
        app.logger.error(f"Lookup error: {e}")
        return jsonify({"error": "Internal lookup error", "verses": []}), 500    

@app.get("/api/intro")
def api_intro():
    book = request.args.get("book", "").strip().lower()
    chapter = request.args.get("chapter", type=int)
    lang = request.args.get("lang", "eng").strip().lower()

    
    # Load from local JSON
    data = _load_book_data(lang)
    if not data:
        return jsonify({"subtitle": "", "introduction": ""})
        
    try:
        # Navigate: Book -> Chapters -> Chapter Number -> "intro"
        book_data = data.get(book, {})
        chapters_data = book_data.get("chapters", {})
        ch_data = chapters_data.get(str(chapter), {})
        
        intro_text = ch_data.get("intro", "")

        return jsonify({
            "subtitle": "", 
            "introduction": intro_text
        })
    except Exception:
        return jsonify({"subtitle": "", "introduction": ""})    

if __name__ == '__main__':
    # Render/Heroku/etc. set PORT in the environment
    port = int(os.getenv("PORT", "5050"))
    app.run(host='0.0.0.0', port=port, debug=False)
