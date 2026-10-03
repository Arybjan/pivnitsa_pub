from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user, get_token_payload, require_admin
from app.database import get_db
from app.schemas.booking import BookingCreate, BookingResponse
from app.services.booking_service import BookingService


router = APIRouter(
    prefix="/api/v1/bookings",
    tags=["Bookings"],
)


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
        return service.create_booking(
            user_id=int(token["sub"]),
            phone=token.get("phone"),
            data=data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

@router.get(
    "/my",
    response_model=list[BookingResponse],
)
def get_my_bookings(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    service = BookingService(db)

    return service.get_user_bookings(user_id)


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    service = BookingService(db)

    booking = service.get_booking(booking_id)

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    if booking.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this booking",
        )

    return booking


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

    return booking


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    service = BookingService(db)

    try:
        booking = service.cancel_booking(
            booking_id=booking_id,
            user_id=user_id,
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

    return booking