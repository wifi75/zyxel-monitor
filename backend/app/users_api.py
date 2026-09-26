"""Utenti del pannello: amministratori e utenti in sola lettura (vedono tutto, non cambiano nulla)."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .core.db import connect
from .core.security import MIN_PASSWORD_LEN, current_user, hash_password, role_of

router = APIRouter(prefix="/api/users")


def admin(user: str = Depends(current_user)) -> str:
    if role_of(user) != "admin":
        raise HTTPException(403, "Serve un utente amministratore")
    return user


class UserIn(BaseModel):
    username: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=MIN_PASSWORD_LEN)
    role: Literal["admin", "viewer"] = "viewer"


@router.get("")
def list_users(_: str = Depends(admin)):
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT username, role FROM users ORDER BY username")]


@router.post("", status_code=201)
def create_user(body: UserIn, _: str = Depends(admin)):
    with connect() as db:
        if db.execute("SELECT 1 FROM users WHERE lower(username) = lower(?)", (body.username,)).fetchone():
            raise HTTPException(409, "Utente già esistente")
        db.execute("INSERT INTO users(username, password_hash, is_default, role) VALUES (?,?,0,?)",
                   (body.username, hash_password(body.password), body.role))
    return {"username": body.username, "role": body.role}


@router.delete("/{username}")
def delete_user(username: str, me: str = Depends(admin)):
    if username == me:
        raise HTTPException(400, "Non puoi eliminare l'utente con cui sei entrato")
    with connect() as db:
        others = db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND username <> ?",
                            (username,)).fetchone()[0]
        if not others:
            raise HTTPException(400, "Deve restare almeno un amministratore")
        db.execute("DELETE FROM users WHERE username = ?", (username,))
    return {"ok": True}
