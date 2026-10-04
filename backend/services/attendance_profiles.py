from __future__ import annotations

from dataclasses import dataclass

from backend.schemas.attendance import AttendanceStateProfileRead


@dataclass(frozen=True, slots=True)
class StateRequirementProfile:
    state_code: str
    state_name: str
    required_days: int | None = None
    required_hours: int | None = None
    show_hours_ui: bool = False

    def to_read(self) -> AttendanceStateProfileRead:
        return AttendanceStateProfileRead(
            state_code=self.state_code,
            state_name=self.state_name,
            required_days=self.required_days,
            required_hours=self.required_hours,
            show_hours_ui=self.show_hours_ui,
        )


_PROFILE_VALUES = (
    ('AL', 'Alabama', 180, None, False),
    ('AK', 'Alaska', None, None, False),
    ('AZ', 'Arizona', None, None, False),
    ('AR', 'Arkansas', None, None, False),
    ('CA', 'California', None, None, False),
    ('CO', 'Colorado', 172, 688, True),
    ('CT', 'Connecticut', 180, None, False),
    ('DE', 'Delaware', None, None, False),
    ('FL', 'Florida', None, None, False),
    ('GA', 'Georgia', 180, 810, True),
    ('HI', 'Hawaii', None, None, True),
    ('ID', 'Idaho', None, None, False),
    ('IL', 'Illinois', None, None, False),
    ('IN', 'Indiana', 180, None, False),
    ('IA', 'Iowa', 148, None, False),
    ('KS', 'Kansas', 186, 1116, True),
    ('KY', 'Kentucky', 185, None, False),
    ('LA', 'Louisiana', 180, None, False),
    ('ME', 'Maine', 175, None, False),
    ('MD', 'Maryland', None, None, False),
    ('MA', 'Massachusetts', None, None, False),
    ('MI', 'Michigan', None, None, False),
    ('MN', 'Minnesota', None, None, False),
    ('MS', 'Mississippi', 180, None, False),
    ('MO', 'Missouri', None, 1000, True),
    ('MT', 'Montana', None, None, True),
    ('NE', 'Nebraska', None, None, True),
    ('NV', 'Nevada', None, None, False),
    ('NH', 'New Hampshire', None, None, False),
    ('NJ', 'New Jersey', None, None, False),
    ('NM', 'New Mexico', 180, None, True),
    ('NY', 'New York', 180, None, True),
    ('NC', 'North Carolina', 180, None, False),
    ('ND', 'North Dakota', 175, 700, True),
    ('OH', 'Ohio', None, 900, True),
    ('OK', 'Oklahoma', 180, None, False),
    ('OR', 'Oregon', None, None, False),
    ('PA', 'Pennsylvania', 180, None, True),
    ('RI', 'Rhode Island', 180, 990, True),
    ('SC', 'South Carolina', 180, 810, True),
    ('SD', 'South Dakota', None, None, True),
    ('TN', 'Tennessee', 180, 720, True),
    ('TX', 'Texas', None, None, False),
    ('UT', 'Utah', None, None, False),
    ('VT', 'Vermont', None, None, False),
    ('VA', 'Virginia', 180, None, False),
    ('WA', 'Washington', 180, 1000, True),
    ('WV', 'West Virginia', 180, None, False),
    ('WI', 'Wisconsin', None, 875, True),
    ('WY', 'Wyoming', None, None, False),
)

STATE_REQUIREMENT_PROFILES = {
    code: StateRequirementProfile(code, name, days, hours, show_hours)
    for code, name, days, hours, show_hours in _PROFILE_VALUES
}


def list_state_requirement_profiles() -> list[AttendanceStateProfileRead]:
    return [profile.to_read() for profile in sorted(STATE_REQUIREMENT_PROFILES.values(), key=lambda item: item.state_name)]


def get_state_requirement_profile(state_code: str) -> StateRequirementProfile | None:
    return STATE_REQUIREMENT_PROFILES.get(state_code.strip().upper())
