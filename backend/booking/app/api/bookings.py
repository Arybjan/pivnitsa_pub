from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import (
    ADMIN_ROLES,
    get_current_user,
    get_token_payload,
    require_admin,
)
from app.database import get_db
from app.schemas.booking import (
    AdminBookingCreate,
    AdminBookingUpdate,
    BookingCancel,
    BookingCreate,
    BookingResponse,
)
from app.services.booking_service import BookingService
from app.models.booking import Booking
from app.services.event_client import EventNotBookable, EventServiceUnavailable
from app.services.venue_client import get_table_details, get_table_numbers


router = APIRouter(
    prefix="/api/v1/bookings",
    tags=["Bookings"],
)


def to_responses(bookings: list[Booking]) -> list[BookingResponse]:
    """Брони с номерами столов и суммами: один запрос к Venue на весь ответ, без N+1."""
    details = get_table_details({booking.table_id for booking in bookings})
    result = []
    for booking in bookings:
        item = BookingResponse.model_validate(booking)
        t_info = details.get(booking.table_id)
        if t_info:
            table_number = t_info.get("number")
            table_price = t_info.get("price")
            total_amount = booking.total_amount
            if total_amount is None and table_price is not None:
                total_amount = Decimal(str(table_price))
            item = item.model_copy(
                update={"table_number": table_number, "total_amount": total_amount}
            )
        result.append(item)
    return result


def to_response(booking: Booking) -> BookingResponse:
    return to_responses([booking])[0]


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
    token: dict = Depends(get_token_payload),
):
    service = BookingService(db)

    try:
        booking = service.create_booking(
            user_id=int(token["sub"]),
            phone=token.get("phone"),
            data=data,
        )

    except EventNotBookable as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    except EventServiceUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event service is unavailable, try again later",
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return to_response(booking)

@router.get(
    "",
    response_model=list[BookingResponse],
)
def list_bookings(
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
    event_id: Annotated[list[int] | None, Query()] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    table_id: int | None = None,
    active: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Брони для администратора. Фильтры складываются через И.

    Брони на мероприятия ищутся по event_id, брони на дату - по date_from/date_to
    (дата по местному времени заведения).
    """
    return to_responses(BookingService(db).list_bookings(
        event_ids=event_id,
        date_from=date_from,
        date_to=date_to,
        table_id=table_id,
        active_only=active,
        limit=limit,
        offset=offset,
    ))


@router.post(
    "/admin",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_booking(
    data: AdminBookingCreate,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    try:
        booking = BookingService(db).create_admin_booking(admin_id, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return to_response(booking)


@router.patch(
    "/{booking_id}",
    response_model=BookingResponse,
)
def update_admin_booking(
    booking_id: int,
    data: AdminBookingUpdate,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    try:
        booking = BookingService(db).update_admin_booking(booking_id, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    return to_response(booking)


@router.get(
    "/my",
    response_model=list[BookingResponse],
)
def get_my_bookings(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    service = BookingService(db)

    return to_responses(service.get_user_bookings(user_id))


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    token: dict = Depends(get_token_payload),
):
    service = BookingService(db)

    booking = service.get_booking(booking_id)

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    if booking.user_id != int(token["sub"]) and token.get("role") not in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this booking",
        )

    return to_response(booking)


@router.post(
    "/{booking_id}/confirm",
    response_model=BookingResponse,
)
def confirm_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    service = BookingService(db)

    try:
        booking = service.confirm_booking(booking_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    return to_response(booking)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    token: dict = Depends(get_token_payload),
    data: Annotated[BookingCancel | None, Body()] = None,
):
    service = BookingService(db)

    try:
        booking = service.cancel_booking(
            booking_id=booking_id,
            user_id=int(token["sub"]),
            is_admin=token.get("role") in ADMIN_ROLES,
            reason=data.reason if data else None,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    return to_response(booking)