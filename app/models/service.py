from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from ..core.database import Base


class Service(Base):
    __tablename__ = "service"
    
    id = Column(Integer, primary_key=True, index=True)
    specialist_id = Column(String, ForeignKey("specialist.user_id"))
    name = Column(String)
    description = Column(String, nullable=True)
    price = Column(String, nullable=True)
    duration = Column(Integer)
    valuta = Column(String, nullable=True)
    
    specialist = relationship("Specialist", back_populates="services")
    direct_appointments = relationship("Appointments", back_populates="service")
    appointment_services = relationship("AppointmentServices", back_populates="service")
