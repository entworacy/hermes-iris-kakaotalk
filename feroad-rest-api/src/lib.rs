pub mod api;
pub mod booking;
pub mod config;
pub mod contract;
pub mod error;
pub mod identity;
pub mod infrastructure;
pub mod organization;
pub mod pot;
pub mod routes;
pub mod shared_kernel;
pub mod supply;

use axum::Router;
use tower_http::{cors::CorsLayer, trace::TraceLayer};

use crate::infrastructure::app_state::AppState;

pub fn create_router() -> Router {
    create_router_with_state(AppState::new())
}

pub fn create_router_with_state(state: AppState) -> Router {
    routes::create_routes(state)
        .layer(TraceLayer::new_for_http())
        .layer(CorsLayer::permissive())
}