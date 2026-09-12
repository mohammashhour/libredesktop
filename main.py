from fastapi import FastAPI, Form, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from pylibrelinkup import PyLibreLinkUp
import secrets

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=secrets.token_hex(32)
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="pages")

sessions = {}

def librelink_login(email, password):
    try:
        client = PyLibreLinkUp(email=email,password=password)
        client.authenticate()
        return client
    except Exception as e:
        print("LibreLinkUp login error:", e)
        return None


def get_patient_name(patient):
    for attribute in ["name", "patient_name", "first_name"]:
        value = getattr(patient, attribute, None)
        if value:
            return str(value)

    return str(patient)


def get_glucose(client, patient):
    reading = client.latest(patient_identifier=patient)
    return {
        "value": reading.value,
        "trend": reading.trend.name
    }

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html"
    )

@app.get("/loginpage")
async def loginpage(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html"
    )

@app.post("/login")
async def login(
    request: Request,
    Email: str = Form(...),
    password: str = Form(...)
):

    if not Email or not password:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "You must fill in all the fields"
            }
        )

    client = librelink_login(
        Email,
        password
    )

    if client is None:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Invalid email or password"
            }
        )

    try:
        patient_list = client.get_patients()

        if not patient_list:
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "error": "No patients were found"
                }
            )

    except Exception as e:

        print("Patient error:", e)

        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Could not retrieve patients"
            }
        )
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {"client": client,"patients": patient_list}
    request.session["session_id"] = session_id
    return RedirectResponse(
        "/dashboard",
        status_code=303
    )

@app.get("/dashboard")
async def dashboard(request: Request):
    session_id = request.session.get("session_id")
    if not session_id or session_id not in sessions:
        return RedirectResponse(
            "/loginpage",
            status_code=303
        )
    session = sessions[session_id]

    patients = []

    for index, patient in enumerate(session["patients"]):

        patients.append({
            "index": index,
            "name": get_patient_name(patient)
        })

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "patients": patients
        }
    )

@app.get("/api/glucose")
async def glucose(
    request: Request,
    patient: int = 0
):

    session_id = request.session.get("session_id")

    if not session_id or session_id not in sessions:
        return JSONResponse(
            {
                "error": "Not logged in"
            },
            status_code=401
        )

    session = sessions[session_id]

    patients = session["patients"]

    if patient < 0 or patient >= len(patients):
        return JSONResponse(
            {
                "error": "Invalid patient"
            },
            status_code=400
        )
    selected_patient = patients[patient]
    try:
        data = get_glucose(
            session["client"],
            selected_patient
        )
        return {
            "value": data["value"],
            "trend": data["trend"],
            "patient": get_patient_name(selected_patient)
        }
    except Exception as e:
        print("Glucose error:", e)
        return JSONResponse(
            {
                "error": "Could not retrieve glucose"
            },
            status_code=500
        )

@app.get("/logout")
async def logout(request: Request):
    session_id = request.session.get("session_id")
    if session_id:
        sessions.pop(session_id, None)
    request.session.clear()
    return RedirectResponse(
        "/loginpage",
        status_code=303
    )