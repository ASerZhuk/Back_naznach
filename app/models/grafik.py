from sqlalchemy import Column, Integer, String, ForeignKey, ARRAY
from sqlalchemy.orm import relationship
from ..core.database import Base


class Grafik(Base):
    __tablename__ = "grafik"
    
    id = Column(Integer, primary_key=True, index=True)
    specialist_id = Column(String, ForeignKey("specialist.user_id"))
    day_of_week = Column(Integer, nullable=True)  # 1-7 (понедельник-воскресенье)
    specific_date = Column(String, nullable=True)  # "YYYY-MM-DD" для конкретных дат
    grafik_type = Column(String, default="work_schedule")  # "work_schedule" или "available_slots"
    
    # Для графика рабочего времени
    start_time = Column(String, nullable=True)  # "09:00"
    end_time = Column(String, nullable=True)    # "18:00"
    
    # Для графика доступных слотов
    time_slots = Column(ARRAY(String), nullable=True)  # ["09:00", "10:00", "14:00", "15:00"]
    
    grafik_name = Column(String, nullable=True)
    
    specialist = relationship("Specialist", back_populates="grafiks")
