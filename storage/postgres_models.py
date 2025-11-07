"""
Модели данных для PostgreSQL
Управление пользователями, авторизацией и настройками
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, 
    Text, JSON, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_activity = Column(DateTime, nullable=True)
    
    # Настройки пользователя
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    
    # Статистика использования
    usage_stats = relationship("UserUsageStats", back_populates="user", uselist=False)
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username='{self.username}')>"


class UserSettings(Base):
    """Настройки пользователя"""
    __tablename__ = 'user_settings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    
    # Настройки уведомлений
    notifications_enabled = Column(Boolean, default=True)
    
    # Настройки анализа
    preferred_language = Column(String(10), default='ru')
    default_priority_filter = Column(String(20), default='all')
    default_read_filter = Column(String(20), default='all')
    
    # Настройки экспорта
    export_format = Column(String(10), default='pdf')
    include_summaries = Column(Boolean, default=True)
    
    # JSON поле для дополнительных настроек
    custom_settings = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Связи
    user = relationship("User", back_populates="settings")
    
    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id})>"


class UserUsageStats(Base):
    """Статистика использования пользователем"""
    __tablename__ = 'user_usage_stats'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    
    # Общая статистика
    total_analyses = Column(Integer, default=0)
    total_exports = Column(Integer, default=0)
    total_commands = Column(Integer, default=0)
    
    # Статистика по приоритетам
    priority_high_count = Column(Integer, default=0)
    priority_medium_count = Column(Integer, default=0)
    priority_low_count = Column(Integer, default=0)
    
    # Статистика по сложности
    complexity_beginner_count = Column(Integer, default=0)
    complexity_intermediate_count = Column(Integer, default=0)
    complexity_advanced_count = Column(Integer, default=0)
    
    # Средние показатели
    avg_relevance_score = Column(Integer, default=0)  # Умножено на 100 для хранения как int
    avg_reading_time = Column(Integer, default=0)  # В минутах
    
    # Временные метки
    first_analysis = Column(DateTime, nullable=True)
    last_analysis = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Связи
    user = relationship("User", back_populates="usage_stats")
    
    def __repr__(self):
        return f"<UserUsageStats(user_id={self.user_id}, total_analyses={self.total_analyses})>"


class AdminAction(Base):
    """Лог административных действий"""
    __tablename__ = 'admin_actions'
    
    id = Column(Integer, primary_key=True)
    admin_telegram_id = Column(Integer, nullable=False, index=True)
    target_telegram_id = Column(Integer, nullable=True, index=True)
    action_type = Column(String(50), nullable=False)  # add_user, remove_user, etc.
    description = Column(Text, nullable=True)
    action_metadata = Column(JSON, default=dict)  # Дополнительные данные
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Индексы
    __table_args__ = (
        Index('idx_admin_actions_admin_created', 'admin_telegram_id', 'created_at'),
        Index('idx_admin_actions_target_created', 'target_telegram_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<AdminAction(admin_id={self.admin_telegram_id}, action='{self.action_type}')>"


class UserSession(Base):
    """Сессии пользователей для отслеживания активности"""
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_start = Column(DateTime, default=func.now(), nullable=False)
    session_end = Column(DateTime, nullable=True)
    commands_count = Column(Integer, default=0)
    analyses_count = Column(Integer, default=0)
    
    # Связи
    user = relationship("User")
    
    # Индексы
    __table_args__ = (
        Index('idx_user_sessions_user_start', 'user_id', 'session_start'),
    )
    
    def __repr__(self):
        return f"<UserSession(user_id={self.user_id}, start={self.session_start})>" 