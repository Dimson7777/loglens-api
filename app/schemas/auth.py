from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in_seconds: int
    refresh_expires_in_seconds: int


class LoginResponse(BaseModel):
    token: TokenResponse


class OAuth2TokenResponse(BaseModel):
    """Flat RFC 6749 token payload for the OAuth2 password flow used by Swagger UI.

    Swagger reads `access_token` from the top level of the response, so this
    cannot reuse the nested `LoginResponse` shape.
    """

    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class LogoutResponse(BaseModel):
    status: str = "ok"


class AuthenticatedUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str
    is_active: bool
