from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(100), nullable=False)
    product_name = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(30), default="PENDING")
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )