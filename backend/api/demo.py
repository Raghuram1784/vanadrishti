from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix='/api/demo/scenarios', tags=['demo'])


@router.get('')
def scenarios(request: Request):
    return {'simulated': True, 'scenarios': [
        {key: data[key] for key in ('scenario_id', 'title', 'description', 'expected_risk_level')}
        | {'simulated': True} for data in request.app.state.context.scenarios().values()]}


@router.post('/{scenario_id}/run')
def run(scenario_id: str, request: Request):
    try:
        return request.app.state.context.run_scenario(scenario_id)
    except KeyError:
        raise HTTPException(404, 'Unknown scenario') from None
