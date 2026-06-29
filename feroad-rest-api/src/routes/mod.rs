mod health;

use axum::{routing::get, Router};

pub fn create_routes() -> Router {
    Router::new()
        .route("/health", get(health::health_check))
        .nest("/api/v1", api_v1_routes())
}

fn api_v1_routes() -> Router {
    Router::new().route("/health", get(health::health_check))
}