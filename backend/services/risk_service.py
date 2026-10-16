"""API alert policy adapter. Scores and reasons remain Phase 3 outputs."""
from ml.context import RiskEngine
from ml.context.models import RiskAssessment


def present_risk(assessment):
    alert = assessment.risk_level in ('HIGH', 'CRITICAL')
    return {'score': assessment.risk_score, 'level': assessment.risk_level,
            'alert': alert, 'reasons': assessment.reasons,
            'recommended_action': (
                'Review evidence and notify ranger supervisor for response.'
                if alert else assessment.recommended_action)}


def apply_zone_policy(assessment, object_type: str, policy: str | None):
    """
    Applies the operational zone policy to human or vehicular detections.
    Biological wildlife rules and any existing high wildlife risk are 100% preserved.
    """
    if not policy:
        return assessment
    policy_upper = policy.upper()
    if policy_upper not in ('SAFE', 'RESTRICTED', 'CRITICAL'):
        return assessment

    # Animal detections always keep their original biological evaluation
    if object_type == 'animal':
        return assessment

    # Human or vehicle detections: apply zone policy modifier
    score = assessment.risk_score
    level = assessment.risk_level
    alert = assessment.alert
    action = assessment.recommended_action
    reasons = list(assessment.reasons)

    label = 'Person' if object_type == 'person' else 'Vehicle'

    if policy_upper == 'SAFE':
        # SAFE / PUBLIC area: Log observation without urgent notification
        score = min(score, 20)
        level = 'LOW'
        alert = False
        reasons.append(
            f"Zone policy: SAFE / PUBLIC — {label} observation logged for routine monitoring; no urgent patrol notification required."
        )
        action = "Log event for routine activity monitoring."
    elif policy_upper == 'RESTRICTED':
        # RESTRICTED area: HIGH risk, create ranger-review notification
        score = max(score, 65)
        level = 'HIGH' if score < 75 else 'CRITICAL'
        alert = True
        reasons.append(
            f"Zone policy: RESTRICTED — {label} detected in restricted perimeter; ranger review notification generated."
        )
        action = "Review evidence and notify field patrol for perimeter check."
    elif policy_upper == 'CRITICAL':
        # CRITICAL / SENSITIVE area: CRITICAL risk, prioritize ranger review
        score = max(score, 85)
        level = 'CRITICAL'
        alert = True
        reasons.append(
            f"Zone policy: CRITICAL / SENSITIVE — Priority {label.lower()} presence in high-security sanctuary sector."
        )
        action = "Immediate ranger review and rapid response dispatch required."

    return RiskAssessment(
        event_id=assessment.event_id,
        risk_score=score,
        risk_level=level,
        alert=alert,
        reasons=reasons,
        recommended_action=action,
    )


class RiskService:
    def __init__(self, context):
        self.engine = RiskEngine(context_engine=context)

    def evaluate(self, event, camera=None, zone_policy=None):
        raw = self.engine.evaluate(event, camera=camera)
        policy = zone_policy or getattr(camera, 'policy', None)
        modified = apply_zone_policy(raw, event.object_type, policy)
        return present_risk(modified)

    def empty(self):
        level, _, action = self.engine.get_risk_level_info(0)
        return {'score': 0, 'level': level, 'alert': False,
                'reasons': ['No retained detections.'], 'recommended_action': action}
