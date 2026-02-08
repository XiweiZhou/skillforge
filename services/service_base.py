#!/usr/bin/env python3
"""
Service Base Classes
Abstract interfaces for MCP and API services
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class ServiceResponse:
    """Response from a service call"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ServiceClient(ABC):
    """Abstract base class for service clients"""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the service"""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the service"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected"""
        pass


class CalendarService(ServiceClient):
    """Abstract base class for calendar services"""

    @abstractmethod
    def get_availability(self, date: str, participant_emails: List[str]) -> ServiceResponse:
        """Get availability for given date and participants"""
        pass

    @abstractmethod
    def schedule_meeting(self, title: str, start_time: str, end_time: str,
                        participants: List[str]) -> ServiceResponse:
        """Schedule a meeting"""
        pass

    @abstractmethod
    def get_conflicts(self, start_time: str, end_time: str) -> ServiceResponse:
        """Check for scheduling conflicts"""
        pass

    @abstractmethod
    def get_participant_preferences(self, participant_email: str) -> ServiceResponse:
        """Get participant preferences"""
        pass


class TimeZoneService(ServiceClient):
    """Abstract base class for timezone services"""

    @abstractmethod
    def convert_time(self, time: str, from_tz: str, to_tz: str) -> ServiceResponse:
        """Convert time between timezones"""
        pass

    @abstractmethod
    def get_timezone(self, location: str) -> ServiceResponse:
        """Get timezone for a location"""
        pass


class SearchService(ServiceClient):
    """Abstract base class for search services"""

    @abstractmethod
    def search(self, query: str) -> ServiceResponse:
        """Perform a web search"""
        pass

    @abstractmethod
    def get_source_credibility(self, url: str) -> ServiceResponse:
        """Get credibility score for a source"""
        pass


if __name__ == "__main__":
    print("Service base classes defined")
