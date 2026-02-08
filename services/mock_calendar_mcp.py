#!/usr/bin/env python3
"""
Mock Calendar MCP Service
Simulates a calendar service for development and testing
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from services.service_base import CalendarService, ServiceResponse
import random

logger = logging.getLogger("MockCalendarMCP")


class MockCalendarMCP(CalendarService):
    """Mock calendar service that simulates MCP responses"""

    def __init__(self):
        """Initialize mock calendar service"""
        self._connected = False

        # Mock participant preferences
        self.preferences = {
            'john@example.com': {
                'preferred_times': ['10:00', '14:00', '15:00'],
                'timezone': 'EST',
                'meeting_duration': 60,
                'min_notice': 24,
            },
            'jane@example.com': {
                'preferred_times': ['09:00', '13:00', '14:00'],
                'timezone': 'PST',
                'meeting_duration': 45,
                'min_notice': 48,
            },
            'bob@example.com': {
                'preferred_times': ['11:00', '15:00', '16:00'],
                'timezone': 'CST',
                'meeting_duration': 30,
                'min_notice': 12,
            },
        }

        # Mock calendar data (simple slots)
        self.calendar_slots = {
            'john@example.com': {
                '2026-02-10': ['09:00', '10:00', '14:00', '14:30', '15:00', '16:00'],
                '2026-02-11': ['10:00', '11:00', '13:00', '14:00', '15:00'],
                '2026-02-12': ['09:30', '10:00', '14:00', '15:00', '15:30'],
            },
            'jane@example.com': {
                '2026-02-10': ['09:00', '10:00', '13:00', '14:00', '16:00'],
                '2026-02-11': ['09:00', '13:00', '13:30', '14:00', '15:00'],
                '2026-02-12': ['09:00', '11:00', '13:00', '14:00'],
            },
            'bob@example.com': {
                '2026-02-10': ['11:00', '14:00', '15:00', '16:00', '16:30'],
                '2026-02-11': ['10:00', '11:00', '14:00', '15:00', '15:30'],
                '2026-02-12': ['11:00', '11:30', '14:00', '15:00', '16:00'],
            },
        }

    def connect(self) -> bool:
        """Connect to service"""
        self._connected = True
        logger.info("Connected to Mock Calendar MCP")
        return True

    def disconnect(self) -> bool:
        """Disconnect from service"""
        self._connected = False
        logger.info("Disconnected from Mock Calendar MCP")
        return True

    def is_connected(self) -> bool:
        """Check connection status"""
        return self._connected

    def get_availability(self, date: str, participant_emails: List[str]) -> ServiceResponse:
        """
        Get availability for participants on given date

        Returns:
            ServiceResponse with available time slots
        """
        if not self._connected:
            return ServiceResponse(success=False, error="Not connected to service")

        try:
            available_slots = None

            # Find common available slots
            for email in participant_emails:
                if email not in self.calendar_slots:
                    continue

                slots = self.calendar_slots[email].get(date, [])
                if available_slots is None:
                    available_slots = set(slots)
                else:
                    available_slots = available_slots.intersection(set(slots))

            available_slots = sorted(list(available_slots or []))

            return ServiceResponse(
                success=True,
                data={
                    'date': date,
                    'participants': participant_emails,
                    'available_slots': available_slots,
                    'num_slots': len(available_slots),
                },
                metadata={'service': 'calendar_mcp', 'timestamp': datetime.now().isoformat()}
            )

        except Exception as e:
            return ServiceResponse(success=False, error=str(e))

    def schedule_meeting(self, title: str, start_time: str, end_time: str,
                        participants: List[str]) -> ServiceResponse:
        """
        Schedule a meeting

        Returns:
            ServiceResponse with scheduling result
        """
        if not self._connected:
            return ServiceResponse(success=False, error="Not connected to service")

        try:
            # Check for conflicts
            conflicts = []

            for participant in participants:
                if participant in self.calendar_slots:
                    # Simple conflict check
                    if start_time in self.calendar_slots[participant].get('2026-02-10', []):
                        if random.random() < 0.1:  # 10% chance of false conflict
                            conflicts.append(participant)

            if conflicts:
                return ServiceResponse(
                    success=False,
                    error=f"Scheduling conflict with {', '.join(conflicts)}",
                    data={'conflicting_participants': conflicts}
                )

            # Schedule successful
            return ServiceResponse(
                success=True,
                data={
                    'meeting_id': f"meet_{hash(title) % 10000:04d}",
                    'title': title,
                    'start_time': start_time,
                    'end_time': end_time,
                    'participants': participants,
                    'status': 'scheduled',
                },
                metadata={'service': 'calendar_mcp', 'timestamp': datetime.now().isoformat()}
            )

        except Exception as e:
            return ServiceResponse(success=False, error=str(e))

    def get_conflicts(self, start_time: str, end_time: str) -> ServiceResponse:
        """
        Check for scheduling conflicts

        Returns:
            ServiceResponse with conflict information
        """
        if not self._connected:
            return ServiceResponse(success=False, error="Not connected to service")

        # In mock, rarely return conflicts (they get learned!)
        has_conflicts = random.random() < 0.05

        return ServiceResponse(
            success=True,
            data={
                'start_time': start_time,
                'end_time': end_time,
                'has_conflicts': has_conflicts,
                'conflict_details': [] if not has_conflicts else ['Sample conflict'],
            },
            metadata={'service': 'calendar_mcp', 'timestamp': datetime.now().isoformat()}
        )

    def get_participant_preferences(self, participant_email: str) -> ServiceResponse:
        """
        Get participant preferences

        Returns:
            ServiceResponse with preference data
        """
        if not self._connected:
            return ServiceResponse(success=False, error="Not connected to service")

        prefs = self.preferences.get(participant_email, {
            'timezone': 'UTC',
            'preferred_times': ['10:00', '14:00'],
            'meeting_duration': 60,
        })

        return ServiceResponse(
            success=True,
            data=prefs,
            metadata={'service': 'calendar_mcp', 'timestamp': datetime.now().isoformat()}
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test the mock service
    service = MockCalendarMCP()
    service.connect()

    # Test availability
    result = service.get_availability('2026-02-10', ['john@example.com', 'jane@example.com'])
    print(f"Availability: {result.data}")

    # Test scheduling
    result = service.schedule_meeting(
        'Team Meeting',
        '10:00',
        '11:00',
        ['john@example.com', 'jane@example.com']
    )
    print(f"Schedule: {result.data if result.success else result.error}")

    service.disconnect()
