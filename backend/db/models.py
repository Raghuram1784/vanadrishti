"""Minimal prototype alert workflow; terminal states cannot be reopened."""
TRANSITIONS = {
    'NEW': {'REVIEWING', 'FALSE_ALARM', 'ESCALATED', 'RESOLVED'},
    'REVIEWING': {'PATROL_ASSIGNED', 'FALSE_ALARM', 'ESCALATED', 'RESOLVED'},
    'PATROL_ASSIGNED': {'ESCALATED', 'FALSE_ALARM', 'RESOLVED'},
    'ESCALATED': {'REVIEWING', 'PATROL_ASSIGNED', 'FALSE_ALARM', 'RESOLVED'},
    'FALSE_ALARM': set(),
    'RESOLVED': set(),
}
