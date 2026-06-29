use axum::{
    body::Body,
    http::{Request, StatusCode},
};
use chrono::NaiveDate;
use feroad_rest_api::create_router_with_state;
use feroad_rest_api::infrastructure::app_state::AppState;
use feroad_rest_api::organization::domain::model::organization::{Organization, OrganizationType};
use feroad_rest_api::shared_kernel::value_objects::{GeoPoint, ServiceDate};
use feroad_rest_api::supply::domain::model::route::{Route, StopType};
use http_body_util::BodyExt;
use serde_json::json;
use tower::ServiceExt;
use uuid::Uuid;

#[tokio::test]
async fn list_catalog_routes_and_create_booking() {
    let state = AppState::new();
    let org = Organization::new(OrganizationType::Operator).verify();
    state.acl.seed_verified_operator(org.id());

    let mut route = Route::new_catalog_fixed(org.id(), "morning shuttle");
    route.add_stop(
        StopType::Pickup,
        GeoPoint::new(37.5, 127.0).unwrap(),
        "A",
    );
    route.add_schedule(
        ServiceDate::new(NaiveDate::from_ymd_opt(2026, 7, 1).unwrap()),
        chrono::NaiveTime::from_hms_opt(8, 0, 0).unwrap(),
    );
    route.activate().unwrap();
    let route_id = route.id();
    state.routes.write().unwrap().insert(route_id, route);

    let app = create_router_with_state(state);
    let rider = Uuid::now_v7();

    let list_response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/api/v1/routes")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(list_response.status(), StatusCode::OK);
    let body = list_response.into_body().collect().await.unwrap().to_bytes();
    let routes: Vec<serde_json::Value> = serde_json::from_slice(&body).unwrap();
    assert_eq!(routes.len(), 1);

    let booking_response = app
        .oneshot(
            Request::builder()
                .method("POST")
                .uri(format!("/api/v1/routes/{}/bookings", route_id.as_uuid()))
                .header("content-type", "application/json")
                .body(Body::from(
                    json!({ "user_id": rider }).to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(booking_response.status(), StatusCode::CREATED);
    let body = booking_response
        .into_body()
        .collect()
        .await
        .unwrap()
        .to_bytes();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(json["status"], "confirmed");
}