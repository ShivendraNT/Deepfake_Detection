"""DEMO-ONLY identity: headers X-Demo-User (employee id) and X-Demo-Role. PRE-IMPLEMENTED.

This is NOT real authentication. Production uses SSO. The console's role switcher sets these
headers. The role must be one the employee actually has in employees.csv.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, Request

from satyapan.api.state import AppState
from satyapan.contracts.enums import Role
from satyapan.contracts.master import Employee


@dataclass
class Actor:
    employee: Employee
    role: Role


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.satyapan
    return state


def get_actor(
    request: Request,
    x_demo_user: str = Header(default="emp_priya"),
    x_demo_role: str = Header(default="maker"),
) -> Actor:
    state = get_state(request)
    user_val = request.query_params.get("user") or request.headers.get("x-demo-user") or x_demo_user
    role_val = request.query_params.get("role") or request.headers.get("x-demo-role") or x_demo_role
    emp = state.master.employee(user_val)
    if emp is None or not emp.active:
        raise HTTPException(status_code=401, detail="unknown demo user")
    try:
        role = Role(role_val)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="unknown role") from e
    if role not in emp.roles:
        raise HTTPException(status_code=403, detail=f"{emp.employee_id} does not have role {role}")
    return Actor(employee=emp, role=role)
