#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""portal.ownpbx.org sign-in / my.ownpbx.org dashboard split.

The login form posts on portal and is redirected to my. Browsers apply the
CSP form-action list to that redirect, so my.ownpbx.org must be in it (else
the browser silently stays on /login). The app's browser sign-in must come
back to /ucp/app/connect on my, and hand the app my.ownpbx.org. Self-hosted
servers (any other host) keep same-host, relative redirects.

    export PBX_DB=/tmp/apptest.db && rm -f $PBX_DB && python3 dev/seed-test-db.py
    python3 dev/test-portal-split.py      # exits non-zero on failure
"""
import os, re, sys
here = os.path.dirname(os.path.abspath(__file__))
os.environ["PBX_NO_BG"] = "1"
sys.path.insert(0, os.path.join(here, "..", "shared"))
sys.path.insert(0, os.path.join(here, "..", "pbx-api"))
from fastapi.testclient import TestClient
import app as A
import bcrypt
A.init_db()
fails = []
def check(n, ok, x=""):
    print(("PASS " if ok else "FAIL ") + n, "" if ok else x); ok or fails.append(n)

d = A.db()
h = bcrypt.hashpw(b"pw-test-12345", bcrypt.gensalt()).decode()
d.execute("UPDATE logins SET pwhash=? WHERE exten='8800'", (h,))
adm = d.execute("SELECT username FROM logins WHERE role='admin' LIMIT 1").fetchone()[0]
d.execute("UPDATE logins SET pwhash=? WHERE username=?", (h, adm)); d.commit()
user = d.execute("SELECT username FROM logins WHERE exten='8800'").fetchone()[0]

def client(host):
    A._login_failures.clear()
    return TestClient(A.app, base_url=f"https://{host}", client=("127.0.0.1", 5555), follow_redirects=False)

# --- portal sign-in lands on my, and the browser is allowed to follow it
p = client("portal.ownpbx.org")
csp = p.get("/login").headers.get("content-security-policy", "")
check("CSP lets the login form redirect to my.ownpbx.org", "form-action" in csp and "https://my.ownpbx.org" in csp, csp)
r = p.post("/login", data={"username": user, "password": "pw-test-12345"})
check("customer -> my.ownpbx.org/ucp", r.headers.get("location") == "https://my.ownpbx.org/ucp", r.headers.get("location"))
ck = r.headers.get("set-cookie", "")
check("session cookie shared with my (domain .ownpbx.org, Secure, Lax)",
      "Domain=.ownpbx.org" in ck and "Secure" in ck and "SameSite=lax" in ck.replace("Lax", "lax"), ck)
r = client("portal.ownpbx.org").post("/login", data={"username": adm, "password": "pw-test-12345"})
check("admin -> my.ownpbx.org/", r.headers.get("location") == "https://my.ownpbx.org/", r.headers.get("location"))

# --- the app's browser sign-in (opens my.ownpbx.org/ucp/app/connect?st=...)
m = client("my.ownpbx.org")
r = m.get("/ucp/app/connect?st=abcdefgh12345")
loc = r.headers.get("location", "")
check("signed out on my -> portal login that remembers the connect page",
      loc.startswith("https://portal.ownpbx.org/login?next=") and "app%2Fconnect" in loc, loc)
r = client("portal.ownpbx.org").post("/login", data={"username": user, "password": "pw-test-12345",
                                                     "next": "/ucp/app/connect?st=abcdefgh12345"})
check("after sign-in -> back to the connect page on my",
      r.headers.get("location") == "https://my.ownpbx.org/ucp/app/connect?st=abcdefgh12345", r.headers.get("location"))
m = client("my.ownpbx.org")
m.cookies.set("pbx_session", r.cookies.get("pbx_session") or re.search(r"pbx_session=([^;]+)", r.headers.get("set-cookie", "")).group(1))
t = m.get("/ucp/app/connect?st=abcdefgh12345").text
check("connect page hands the app my.ownpbx.org", "s=https%3A%2F%2Fmy.ownpbx.org" in t or "s=https://my.ownpbx.org" in t, t[:400])
r = m.get("/login")
check("already signed in, /login -> dashboard on my", r.headers.get("location") == "https://my.ownpbx.org/ucp", r.headers.get("location"))
r = client("my.ownpbx.org").get("/ucp/settings")
check("other pages: plain portal login (no open redirect)", r.headers.get("location") == "https://portal.ownpbx.org/login", r.headers.get("location"))
r = client("my.ownpbx.org").get("/login?out=1")
check("signed-out /login keeps ?out=1", r.headers.get("location") == "https://portal.ownpbx.org/login?out=1", r.headers.get("location"))
r = client("portal.ownpbx.org").post("/login", data={"username": user, "password": "pw-test-12345", "next": "https://evil.example/"})
check("a foreign next is ignored", r.headers.get("location") == "https://my.ownpbx.org/ucp", r.headers.get("location"))

# --- self-hosted: unchanged
s = client("pbx.example.com")
check("self-hosted CSP is form-action 'self' only", "my.ownpbx.org" not in s.get("/login").headers.get("content-security-policy", ""))
r = s.post("/login", data={"username": user, "password": "pw-test-12345"})
check("self-hosted -> relative /ucp, host-only cookie", r.headers.get("location") == "/ucp" and "Domain=" not in r.headers.get("set-cookie", ""),
      (r.headers.get("location"), r.headers.get("set-cookie")))
print("FAILED:", ", ".join(fails) or "none")
sys.exit(1 if fails else 0)
