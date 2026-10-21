
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    document: str | None = Field(default=None, min_length=11, max_length=14)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    document: str | None = Field(default=None, min_length=11, max_length=14)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)


class CustomerResponse(BaseModel):
    id: int
    name: str
    document: str | None
    email: str | None
    phone: str | None

    model_config = ConfigDict(from_attributes=True)
