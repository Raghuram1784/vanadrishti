"""API alert policy adapter. Scores and reasons remain Phase 3 outputs."""
from ml.context import RiskEngine


def present_risk(assessment):
    alert = assessment.risk_level in ('HIGH', 'CRITICAL')
    return {'score': assessment.risk_score, 'level': assessment.risk_level,
            'alert': alert, 'reasons': assessment.reasons,
            'recommended_action': (
                'Review evidence and notify ranger supervisor for response.'
                if alert else assessment.recommended_action)}


class RiskService:
    def __init__(self, context):
        self.engine = RiskEngine(context_engine=context)

    def evaluate(self, event, camera):
        return present_risk(self.engine.evaluate(event, camera=camera))

    def empty(self):
        level, _, action = self.engine.get_risk_level_info(0)
        return {'score': 0, 'level': level, 'alert': False,
                'reasons': ['No retained detections.'], 'recommended_action': action}
