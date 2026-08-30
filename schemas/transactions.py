import datetime
from decimal import Decimal
from typing import Any
from typing import Dict
from typing import Optional
from typing import Union

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from core.util import convert_to_date


def _parse_coordinate(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float, Decimal)):
        return float(v)
    if isinstance(v, str):
        v = v.strip().replace(",", ".")
        try:
            return float(v)
        except ValueError:
            raise ValueError(f"Invalid coordinate format: {v}")
    raise ValueError(f"Invalid coordinate format: {v}")


def _get_first_coordinate_value(data: Dict[str, Any], *keys: str) -> Any:
    """Return the first provided coordinate value, including zero."""
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


class Location(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude between -90 and 90")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude between -180 and 180")


class Transaction(BaseModel):
    account: str = Field(..., description="Account name or ID is required")
    amount: Decimal = Field(default=Decimal(0), description="Transaction amount")
    date: datetime.date = Field(
        default_factory=datetime.date.today,
        description="Transaction date in formats: YYYY-MM-DD, MMM DD, YYYY, or MMM DD YYYY",
    )
    payee: Optional[str] = None
    notes: Optional[str] = None
    cleared: bool = False
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Latitude between -90 and 90")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Longitude between -180 and 180")
    location: Optional[Union[Location, Dict[str, Any], str]] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_location(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Check aliases at top level: lat, long, lng, lon
        lat = _get_first_coordinate_value(data, "latitude", "lat")
        lon = _get_first_coordinate_value(data, "longitude", "long", "lng", "lon")

        # Check nested location object / string
        loc = data.get("location")
        if loc is not None:
            if isinstance(loc, dict):
                loc_lat = _get_first_coordinate_value(loc, "latitude", "lat")
                loc_lon = _get_first_coordinate_value(loc, "longitude", "long", "lng", "lon")
                if lat is None:
                    lat = loc_lat
                if lon is None:
                    lon = loc_lon
            elif isinstance(loc, Location):
                if lat is None:
                    lat = loc.latitude
                if lon is None:
                    lon = loc.longitude
            elif isinstance(loc, str) and "," in loc:
                parts = loc.split(",")
                if len(parts) == 2:
                    if lat is None:
                        lat = parts[0].strip()
                    if lon is None:
                        lon = parts[1].strip()

        if lat is not None or lon is not None:
            if lat is None or lon is None or lat == "" or lon == "":
                raise ValueError("Both latitude and longitude must be provided.")
            parsed_lat = _parse_coordinate(lat)
            parsed_lon = _parse_coordinate(lon)
            if parsed_lat is not None and not (-90.0 <= parsed_lat <= 90.0):
                raise ValueError("Latitude must be between -90 and 90.")
            if parsed_lon is not None and not (-180.0 <= parsed_lon <= 180.0):
                raise ValueError("Longitude must be between -180 and 180.")
            data["latitude"] = parsed_lat
            data["longitude"] = parsed_lon
            if parsed_lat is not None and parsed_lon is not None:
                data["location"] = Location(latitude=parsed_lat, longitude=parsed_lon)

        return data

    @field_validator("amount", mode="before")
    def validate_amount(cls, v):
        try:
            # Replace comma with period if present
            if isinstance(v, str) and "," in v:
                v = v.replace(",", ".")
            return Decimal(str(v)) if v else Decimal(0)
        except Exception:
            raise ValueError("Invalid amount format. Must be a valid decimal number.")

    @field_validator("date", mode="before")
    def parse_date(cls, value):
        try:
            parsed_date = convert_to_date(value)
            # If convert_to_date returns a datetime object convert it to a date object
            if isinstance(parsed_date, datetime.datetime):
                return parsed_date.date()
            return parsed_date
        except ValueError as e:
            raise ValueError(str(e))
