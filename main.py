import os
import json
import dotenv
import logging
import uvicorn
import numpy as np
import cv2
import pytesseract

from bson import json_util, ObjectId
from pymongo import MongoClient
from healthcheck import HealthCheck
from fastapi import BackgroundTasks, FastAPI, UploadFile

from starlette.responses import FileResponse
from model import extract

# Initialization
dotenv.load_dotenv("config.env")
logging.basicConfig(level=logging.INFO)
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Users\jazib\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
)

app = FastAPI(
    title=os.getenv("TITLE", "Zepp NLP Engine"),
    description=os.getenv("DESCRIPTION", "Extracts coupon details from text"),
    version=os.getenv(
        "VERSION",
        "1.0.0",
    ),
    root_path=os.getenv("PROXY", None),
)

health = HealthCheck()

client = MongoClient(
    os.getenv("MONGO_URI", "mongodb://localhost:27017")
    + "/Zepp?retryWrites=true&w=majority"
)

print("Connected to MongoDB: " + str(client))
logging.info("Connected to MongoDB: " + str(client))
jobs = client.get_default_database().jobs
users = client.get_default_database().users


# Processing
def process_job(text: str, userId: str, job_id: str):
    resp = extract(text)
    users.find_one_and_update({"_id": ObjectId(userId)}, {"$push": {"coupons": resp}})
    jobs.find_one_and_delete({"_id": ObjectId(job_id)})


def parse_json(data):
    return json.loads(json_util.dumps(data))


# API
@app.get("/")
async def healthcheck():
    """Healthcheck endpoint"""
    message, _, _ = health.run()

    return json.loads(message)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("favicon.ico")


@app.get("/jobs")
async def get_all_jobs():
    """All Jobs Data/Status endpoint"""
    try:
        return parse_json(list(jobs.find({})))
    except Exception as e:
        logging.warning(e)
        return {"error": "Internal Undefined Error"}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Job Data/Status endpoint"""
    try:
        return parse_json(jobs.find_one({"_id": ObjectId(job_id)}))
    except Exception as e:
        logging.warning(e)
        return {"error": "Internal Undefined Error"}


@app.post("/jobs/submit")
async def submit_job(text: str, userId: str, background_tasks: BackgroundTasks):
    """Job Submit endpoint"""
    try:
        job = jobs.insert_one({"status": "submitted", "text": text, "userId": userId})
        job_id = str(job.inserted_id)
        background_tasks.add_task(process_job, text=text, userId=userId, job_id=job_id)
        return {"status": "submitted", "id": job_id}
    except Exception as e:
        logging.warning(e)
        return {"status": "error", "id": None}


@app.post("/jobs/ocr")
async def run_ocr(image: UploadFile):
    """Job Submit endpoint"""
    try:
        contents = await image.read()
        nparr = np.fromstring(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        custom_config = r"--oem 3 --psm 6"
        text = pytesseract.image_to_string(img, config=custom_config)

        return {"text": text}
    except Exception as e:
        logging.warning(e)
        return {"status": "error", "details": e}


@app.get("/users")
async def get_all_users():
    """All users Data/Status endpoint"""
    try:
        return parse_json(list(users.find({})))
    except Exception as e:
        logging.warning(e)
        return {"error": "Internal Undefined Error"}


# Application
@app.on_event("shutdown")
def shutdown_event():
    client.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=4000)
