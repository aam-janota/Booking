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
APPOINTMENTS = {}
appointment_id_counter = 1

class AppointmentBase(BaseModel):
    service_id: int
    patient_name: str = Field(..., min_length=2, max_length=50)
    slot_time: datetime

class AppointmentResponse(AppointmentBase):
    id: int
    status: str

def validate_slot(service_id: int, slot_time: datetime):
    # 1. Check if service exists
    if service_id not in SERVICES:
        raise HTTPException(status_code=404, detail="Service not found")
        
    # Standardize the incoming timestamp to safely compare hours without microsecond interference
    naive_slot_time = slot_time.replace(second=0, microsecond=0, tzinfo=None)
    
    # 2. Check for double-booking
    for appt in APPOINTMENTS.values():
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
    global appointment_id_counter
    validate_slot(appointment.service_id, appointment.slot_time)
    
    new_appt = {
        "id": appointment_id_counter,
        "service_id": appointment.service_id,
        "patient_name": appointment.patient_name,
        "slot_time": appointment.slot_time,
        "status": "confirmed"
    }
    APPOINTMENTS[appointment_id_counter] = new_appt
    appointment_id_counter += 1
    return new_appt


@app.get("/appointments", response_model=List[AppointmentResponse])
def list_appointments(service_id: Optional[int] = None):
    if service_id:
        return [v for v in APPOINTMENTS.values() if v["service_id"] == service_id]
    return list(APPOINTMENTS.values())


@app.put("/appointments/{appt_id}/cancel")
def cancel_appointment(appt_id: int):
    if appt_id not in APPOINTMENTS:
        raise HTTPException(status_code=404, detail="Appointment not found")
    APPOINTMENTS[appt_id]["status"] = "cancelled"
    return {"message": "Cancelled"}
