from pathlib import Path # to locate the templates directory
import time # to track the last active time of the user

from fastapi import APIRouter, Request, Form # to handle the request and form data
from fastapi.responses import RedirectResponse # to redirect the user to other pages
from fastapi.templating import Jinja2Templates # to render the templates
from starlette.status import HTTP_302_FOUND # to return the HTTP status code

router = APIRouter() #create a router object
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

# Hardcoded credentials for demo purposes only
# In real applications, credentials come from a database
VALID_USERNAME = "admin"
VALID_PASSWORD = "password"
IDLE_SECONDS = 120 # impletment session timeout, set to 2 minutes


def logged_in(request: Request):
    # Check if the user is logged in and within the idle timeout
    user = request.session.get("user")
    if not user:
        return None
    last_active = request.session.get("last_active")
    now = int(time.time())
    if last_active is None or now - int(last_active) > IDLE_SECONDS:
        request.session.clear()
        return None
    request.session["last_active"] = now # update the last active time
    return user


@router.get("/") # route to the home page
def home(request: Request):
    user = logged_in(request)
    return templates.TemplateResponse(request, "index.html", {"user": user})


@router.get("/login")
def login_page(request: Request):
    user = logged_in(request)
    error = request.session.pop("login_error", None) # pop the login error from the session if it exists
    return templates.TemplateResponse(
        request, "login.html", {"user": user, "error": error}
    )


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """
    Handles login form submission.

    - Reads username and password from the form
    - Validates credentials
    - Stores user info in session if valid
    """
    if username == VALID_USERNAME and password == VALID_PASSWORD:
        request.session["user"] = username # store the username in the session
        request.session["last_active"] = int(time.time()) # set the last active time to now
        request.session.pop("login_error", None) # pop the login error from the session if it exists
        return RedirectResponse(url="/dashboard", status_code=HTTP_302_FOUND)
    # If the credentials are invalid, store the error in the session and redirect to the login page
    request.session["login_error"] = "Invalid username or password."
    return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)


@router.get("/dashboard")
def dashboard(request: Request):
    user = logged_in(request)
    if not user:
        return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)
