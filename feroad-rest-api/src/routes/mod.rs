pub mod health;

use axum::{routing::get, Router};

use crate::api::v1;
use crate::infrastructure::app_state::AppState;

pub fn create_routes(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health::health_check))
        .nest("/api/v1", v1::router())
        .with_state(state)
}