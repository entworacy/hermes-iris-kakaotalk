use axum::{
    body::Body,
    http::{Request, StatusCode},
};
use feroad_rest_api::create_router_with_state;
use feroad_rest_api::infrastructure::app_state::AppState;
use http_body_util::BodyExt;
use serde_json::json;
use tower::ServiceExt;
use uuid::Uuid;

#[tokio::test]
async fn post_intent_returns_201() {
    let app = create_router_with_state(AppState::new());
    let user_id = Uuid::now_v7();

    let response = app
        .oneshot(intent_request(user_id, "08:00:00"))
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::CREATED);

    let body = response.into_body().collect().await.unwrap().to_bytes();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(json["status"], "open");
}

#[tokio::test]
async fn pot_like_flow_spawns_route_via_api() {
    let state = AppState::new();
    let app = create_router_with_state(state.clone());

    let user_a = Uuid::now_v7();
    let user_b = Uuid::now_v7();

    let intent_a = post_intent_id(&app, user_a, "08:00:00").await;
    let intent_b = post_intent_id(&app, user_b, "08:10:00").await;

    like(&app, intent_a, intent_b).await;
    like(&app, intent_b, intent_a).await;

    let pot_id = state
        .pots
        .read()
        .unwrap()
        .keys()
        .next()
        .copied()
        .expect("pot should exist");

    let response = app
        .oneshot(
            Request::builder()
                .uri(format!("/api/v1/pot/pots/{}/route", pot_id.as_uuid()))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);

    let body = response.into_body().collect().await.unwrap().to_bytes();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert!(json["route_type"]
        .as_str()
        .unwrap()
        .contains("Ephemeral"));
}

fn intent_request(user_id: Uuid, time: &str) -> Request<Body> {
    Request::builder()
        .method("POST")
        .uri("/api/v1/pot/intents")
        .header("content-type", "application/json")
        .body(Body::from(
            json!({
                "user_id": user_id,
                "origin": { "lat": 37.5665, "lng": 126.9780 },
                "destination": { "lat": 37.5700, "lng": 126.9820 },
                "service_date": "2026-07-01",
                "departure_time": time,
                "passenger_count": 1
            })
            .to_string(),
        ))
        .unwrap()
}

async fn post_intent_id(app: &axum::Router, user_id: Uuid, time: &str) -> Uuid {
    let response = app
        .clone()
        .oneshot(intent_request(user_id, time))
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::CREATED);
    let body = response.into_body().collect().await.unwrap().to_bytes();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    Uuid::parse_str(json["id"].as_str().unwrap()).unwrap()
}

async fn like(app: &axum::Router, from: Uuid, to: Uuid) {
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri(format!("/api/v1/pot/intents/{to}/like"))
                .header("content-type", "application/json")
                .body(Body::from(
                    json!({ "from_intent_id": from }).to_string(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::NO_CONTENT);
}