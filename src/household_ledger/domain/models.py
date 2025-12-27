from sqlalchemy import String, Numeric, Date, Time, ForeignKey, Text, BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import date, time
from typing import Optional

class Base(DeclarativeBase):
    """SQLAlchemy 모델을 위한 선언적 기본 클래스"""
    pass

class Account(Base):
    """
    사용자 계좌 및 카드 정보 모델 (accounts.csv 매핑)
    """
    __tablename__ = "accounts"
    
    account_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    account_type: Mapped[Optional[str]] = mapped_column(String(50))
    account_description: Mapped[Optional[str]] = mapped_column(Text)
    creation_date: Mapped[Optional[date]] = mapped_column(Date)

class TransactionHistory(Base):
    """
    결제 상세 내역 모델 (transactions.csv 매핑)
    """
    __tablename__ = "transactions"
    
    transaction_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    # Account 테이블과 연결되는 외래키
    account_id: Mapped[str] = mapped_column(String(50), ForeignKey("accounts.account_id"))
    
    # Microsoft 데이터셋 특성상 날짜와 시간이 분리되어 있습니다.
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    transaction_time: Mapped[Optional[time]] = mapped_column(Time)
    
    # 결제 금액 및 가맹점
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    merchant_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    
    # [핵심] LLM이 가맹점명을 분석하여 채워넣을 카테고리 필드
    category: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    
    # 기타 분석용 필드
    transaction_type: Mapped[Optional[str]] = mapped_column(String(50))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    country: Mapped[Optional[str]] = mapped_column(String(50))
    currency: Mapped[Optional[str]] = mapped_column(String(10))