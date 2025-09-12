from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class Appointments(Base):
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    specialist_id = Column(String, ForeignKey("specialist.user_id"))
    service_id = Column(Integer, ForeignKey("service.id"), nullable=True)
    service_name = Column(String, nullable=True)
    service_valuta = Column(String, nullable=True)
    date = Column(String)
    time = Column(String)
    phone = Column(String)
    specialist_name = Column(String, nullable=True)
    specialist_last_name = Column(String, nullable=True)
    specialist_address = Column(String, nullable=True)
    service_price = Column(String, nullable=True)
    specialist_phone = Column(String, nullable=True)
    status = Column(String, default="active")  # active, cancelled, rescheduled
    reminder_sent = Column(Boolean, nullable=True, default=False)
    reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    specialist = relationship("Specialist", back_populates="appointments")
    service = relationship("Service", back_populates="direct_appointments")
    services = relationship("AppointmentServices", back_populates="appointment")


class AppointmentServices(Base):
    __tablename__ = "appointment_services"
    
    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"))
    service_id = Column(Integer, ForeignKey("service.id"))
    
    appointment = relationship("Appointments", back_populates="services")
    service = relationship("Service", back_populates="appointment_services")
