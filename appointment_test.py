import json
import os
from datetime import datetime, time
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Booking Portal Backend", version="1.0.0")

# --- ENABLE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE SIMULATION ---
SERVICES = {
    1: {"name": "Service Beginner", "specialty": "Beginner", "start_hour": time(9, 0), "end_hour": time(17, 0)},
    2: {"name": "Service PRO", "specialty": "PRO", "start_hour": time(10, 0), "end_hour": time(16, 0)}
}

DB_FILE = "appointments_db.json"

def load_db() -> dict:
    """Safely loads appointments from a JSON file into memory."""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            # Convert string keys back to integers and ISO strings back to datetimes
            parsed_data = {}
            for k, v in data.items():
                v["slot_time"] = datetime.fromisoformat(v["slot_time"])
                parsed_data[int(k)] = v
            return parsed_data
    except Exception:
        return {}

def save_db(data: dict):
    """Saves memory state back into the local JSON file securely."""
    serialized_data = {}
    for k, v in data.items():
        # Convert datetime objects to string format so JSON can stringify it safely
        copy_v = v.copy()
        if isinstance(copy_v["slot_time"], datetime):
            copy_v["slot_time"] = copy_v["slot_time"].isoformat()
        serialized_data[str(k)] = copy_v
        
    with open(DB_FILE, "w") as f:
        json.dump(serialized_data, f, indent=4)

class AppointmentBase(BaseModel):
    service_id: int
    patient_name: str = Field(..., min_length=2, max_length=50)
    slot_time: datetime

class AppointmentResponse(AppointmentBase):
    id: int
    status: str

def validate_slot(service_id: int, slot_time: datetime, appointments: dict):
    # 1. Check if service exists
    if service_id not in SERVICES:
        raise HTTPException(status_code=404, detail="Service not found")
        
    # Standardize the incoming timestamp to safely compare hours without microsecond interference
    naive_slot_time = slot_time.replace(second=0, microsecond=0, tzinfo=None)
    
    # 2. Check for double-booking
    for appt in appointments.values():
        # Standardize the existing saved database timestamps the exact same way
        saved_appt_time = appt["slot_time"].replace(second=0, microsecond=0, tzinfo=None)
        
        # If the same service is already booked for this exact minute, throw a conflict error
        if appt["service_id"] == service_id and saved_appt_time == naive_slot_time and appt["status"] != "cancelled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, 
                detail="This time slot is already booked for this service."
            )


@app.get("/services")
def get_services():
    return [{"id": k, **v} for k, v in SERVICES.items()]

@app.post("/appointments", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def book_appointment(appointment: AppointmentBase):
    appointments = load_db()
    validate_slot(appointment.service_id, appointment.slot_time, appointments)
    
    # Generate sequential unique keys based on existing entries to prevent overlaps
    appointment_id_counter = max(appointments.keys()) + 1 if appointments else 1
    
    new_appt = {
        "id": appointment_id_counter,
        "service_id": appointment.service_id,
        "patient_name": appointment.patient_name,
        "slot_time": appointment.slot_time,
        "status": "confirmed"
    }
    
    appointments[appointment_id_counter] = new_appt
    save_db(appointments)
    return new_appt


@app.get("/appointments", response_model=List[AppointmentResponse])
def list_appointments(service_id: Optional[int] = None):
    appointments = load_db()
    if service_id:
        return [v for v in appointments.values() if v["service_id"] == service_id]
    return list(appointments.values())


@app.put("/appointments/{appt_id}/cancel")
def cancel_appointment(appt_id: int):
    appointments = load_db()
    if appt_id not in appointments:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    appointments[appt_id]["status"] = "cancelled"
    save_db(appointments)
    return {"message": "Cancelled"}
