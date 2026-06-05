from pydantic import BaseModel

class OperatorInfo(BaseModel):
    name: str
    country: str
    city: str = ""
    url: str = ""

class Profile(BaseModel):
    profile_type: str
    role: str | None = None
    individual_name: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None

class FetchResult(BaseModel):
    ok: bool
    url: str | None = None
    text: str | None = None
    message: str | None = None
    used_stealth: bool = False

class ParseResult(BaseModel):
    ok: bool
    hyperlink_key_text: str | None = None
    parsed_text: str | None = None
    emails: list[str] | None = None
    phones: list[str] | None = None
    socials: dict[str, str] | None = None # facebook, instagram, youtube, tiktok, x, tripadvisor
    message: str | None = None

class ClassifyResult(BaseModel):
    ok: bool
    description: str | None = None
    operator_type: str | None = None
    business_type: str | None = None
    experience_type: str | None = None
    is_commercial_operator: bool | None = None
    booking_method: str | None = None
    operating_scope: str | None = None
    final_url: str | None = None
    follow_booking: str | None = None
    follow_contact: str | None = None
    profiles: list[Profile] | None = None
    message: str | None = None
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    searched: bool = False
    used_stealth: bool = False

    def merge(self, other: "ClassifyResult") -> None:
        for k in self.__class__.model_fields:
            a, b = getattr(self, k), getattr(other, k)
            if not b:
                continue
            if k in {"input_tokens", "cached_input_tokens", "output_tokens"}:
                setattr(self, k, a + b)
            elif k in {"ok", "searched", "used_stealth"}:
                setattr(self, k, a or b)
            elif k == "profiles":
                setattr(self, k, (a or []) + b)
            elif k == "message":
                setattr(self, k, f"{a} | {b}" if a else b)
            else:
                setattr(self, k, b)

class SearchResult(BaseModel):
    ok: bool
    url: str | None = None
    message: str | None = None