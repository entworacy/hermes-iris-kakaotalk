use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use uuid::Uuid;

use crate::api::v1::pot::dto::{
    geo_from_dto, parse_intent_id, parse_pot_id, parse_user_id, service_date_from, DiscoverQuery,
    IntentResponse, LikeIntentRequest, PostIntentRequest, PotResponse, RouteSummaryResponse,
};
use crate::error::ApiError;
use crate::infrastructure::app_state::AppState;
use crate::pot::application::command::like_intent;
use crate::pot::application::command::post_ride_intent::{self, PostRideIntentCommand};
use crate::pot::application::query::{discover_intents, get_pot};

pub async fn post_intent(
    State(state): State<AppState>,
    Json(body): Json<PostIntentRequest>,
) -> Result<(StatusCode, Json<IntentResponse>), ApiError> {
    let user_id = parse_user_id(body.user_id);
    state.acl.seed_active_user(user_id);

    let origin = geo_from_dto(body.origin).map_err(|e| ApiError::BadRequest(e.into()))?;
    let destination = geo_from_dto(body.destination).map_err(|e| ApiError::BadRequest(e.into()))?;

    let intent = post_ride_intent::handle(
        &state,
        PostRideIntentCommand {
            user_id,
            origin,
            destination,
            service_date: service_date_from(body.service_date),
            departure_time: body.departure_time,
            passenger_count: body.passenger_count,
            corporate_org_id: None,
        },
    )
    .await
    .map_err(ApiError::BadRequest)?;

    Ok((StatusCode::CREATED, Json(IntentResponse::from(intent))))
}

pub async fn discover_intents(
    State(state): State<AppState>,
    Query(query): Query<DiscoverQuery>,
) -> Result<Json<Vec<IntentResponse>>, ApiError> {
    let intents = discover_intents::handle(&state, parse_intent_id(query.for_intent_id))
        .await
        .map_err(ApiError::BadRequest)?;

    Ok(Json(intents.into_iter().map(IntentResponse::from).collect()))
}

pub async fn like_intent(
    State(state): State<AppState>,
    Path(to_intent_id): Path<Uuid>,
    Json(body): Json<LikeIntentRequest>,
) -> Result<StatusCode, ApiError> {
    like_intent::handle(
        &state,
        parse_intent_id(body.from_intent_id),
        parse_intent_id(to_intent_id),
    )
    .await
    .map_err(ApiError::BadRequest)?;

    state
        .dispatch_pending_events()
        .await
        .map_err(ApiError::Internal)?;

    Ok(StatusCode::NO_CONTENT)
}

pub async fn pass_intent(
    State(_state): State<AppState>,
    Path(_intent_id): Path<Uuid>,
) -> Result<StatusCode, ApiError> {
    Ok(StatusCode::NO_CONTENT)
}

pub async fn withdraw_intent(
    State(state): State<AppState>,
    Path(intent_id): Path<Uuid>,
) -> Result<StatusCode, ApiError> {
    let id = parse_intent_id(intent_id);
    let mut intents = state.intents.write().unwrap();
    let intent = intents
        .get_mut(&id)
        .ok_or_else(|| ApiError::NotFound("intent not found".into()))?;
    intent
        .withdraw()
        .map_err(|e| ApiError::BadRequest(e.into()))?;
    Ok(StatusCode::NO_CONTENT)
}

pub async fn get_pot(
    State(state): State<AppState>,
    Path(pot_id): Path<Uuid>,
) -> Result<Json<PotResponse>, ApiError> {
    let pot = get_pot::handle(&state, parse_pot_id(pot_id))
        .await
        .map_err(|_| ApiError::NotFound("pot not found".into()))?;
    Ok(Json(PotResponse::from(pot)))
}

pub async fn get_pot_route(
    State(state): State<AppState>,
    Path(pot_id): Path<Uuid>,
) -> Result<Json<RouteSummaryResponse>, ApiError> {
    let pot = get_pot::handle(&state, parse_pot_id(pot_id))
        .await
        .map_err(|_| ApiError::NotFound("pot not found".into()))?;

    let route_id = pot
        .route_id()
        .ok_or_else(|| ApiError::NotFound("pot has no route yet".into()))?;

    let route = state
        .routes
        .read()
        .unwrap()
        .get(&route_id)
        .cloned()
        .ok_or_else(|| ApiError::NotFound("route not found".into()))?;

    Ok(Json(RouteSummaryResponse::from(route)))
}