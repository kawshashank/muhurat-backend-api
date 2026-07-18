from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# Initialize the app
app = FastAPI(title="Vijayshwar Jantri - Muhurat API")

# CRITICAL: CORS Configuration
# This allows your Next.js Vercel app to communicate with this backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, we will lock this down to your vercel.app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the expected incoming JSON payload from Next.js
class MuhuratRequest(BaseModel):
    activity: str
    target_year: int
    selected_zone_name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None

@app.get("/")
def read_root():
    return {"status": "online", "message": "Muhurat API is awake and running!"}

@app.post("/api/calculate-muhurat")
def calculate_muhurat(request: MuhuratRequest):
    # This is a skeleton response to verify the connection
    # We will inject the ephem astronomical logic here next
    return {
        "status": "success",
        "echo_params": {
            "activity": request.activity,
            "timezone": request.selected_zone_name,
            "year": request.target_year
        },
        "results": [
            {
                "date": "2026-08-15",
                "start_time": "08:30",
                "end_time": "11:45",
                "nakshatra": "Pushya",
                "tithi": "Ashtami",
                "notes": "Rahu Kaal avoided."
            }
        ]
    }