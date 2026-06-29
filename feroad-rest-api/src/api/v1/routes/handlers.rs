use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use serde::Deserialize;
use uuid::Uuid;

use crate::api::v1::pot::dto::{parse_route_id, parse_user_id, RouteSummaryResponse};
use crate::booking::application::command::request_catalog_booking;
use crate::booking::domain::model::booking::BookingStatus;
use crate::error::ApiError;
use crate::infrastructure::app_state::AppState;

#[derive(Debug, Deserialize)]
pub struct CatalogBookingRequest {
    pub user_id: Uuid,
}

#[derive(Debug, serde::Serialize)]
pub struct BookingResponse {
    pub id: Uuid,
    pub route_id: Uuid,
    pub status: String,
}

pub async fn list_catalog_routes(
    State(state): State<AppState>,
) -> Result<Json<Vec<RouteSummaryResponse>>, ApiError> {
    let routes: Vec<RouteSummaryResponse> = state
        .routes
        .read()
        .unwrap()
        .values()
        .filter(|r| r.is_catalog_listing())
        .cloned()
        .map(RouteSummaryResponse::from)
        .collect();

    Ok(Json(routes))
}

pub async fn create_catalog_booking(
    State(state): State<AppState>,
    Path(route_id): Path<Uuid>,
    Json(body): Json<CatalogBookingRequest>,
) -> Result<(StatusCode, Json<BookingResponse>), ApiError> {
    let user_id = parse_user_id(body.user_id);
    state.acl.seed_active_user(user_id);

    let booking = request_catalog_booking::handle(&state, user_id, parse_route_id(route_id))
        .await
        .map_err(ApiError::BadRequest)?;

    state
        .dispatch_pending_events()
        .await
        .map_err(ApiError::Internal)?;

    let status = match booking.status() {
        BookingStatus::Confirmed => "confirmed",
        BookingStatus::PendingApproval => "pending_approval",
        BookingStatus::Requested => "requested",
        BookingStatus::Cancelled => "cancelled",
        BookingStatus::Completed => "completed",
    };

    Ok((
        StatusCode::CREATED,
        Json(BookingResponse {
            id: booking.id().as_uuid(),
            route_id: booking.route_id().as_uuid(),
            status: status.into(),
        }),
    ))
}