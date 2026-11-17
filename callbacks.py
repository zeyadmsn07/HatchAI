"""Thin wrapper around db.log_action so agents don't import db directly."""
import db


def log(run_id, agent, action, sources=None, model=None, cost=0,
        approved_by=None, phase=None, outcome=None, tokens=None):
    db.log_action(
        run_id=run_id,
        agent=agent,
        action=action,
        sources=sources,
        model=model,
        cost=cost,
        approved_by=approved_by,
        phase=phase,
        outcome=outcome,
        tokens=tokens,
    )
