pub mod pot;
pub mod routes;

use axum::{
    routing::{delete, get, post},
    Router,
};

use crate::infrastructure::app_state::AppState;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/health", get(crate::routes::health::health_check))
        .route("/pot/intents", post(pot::handlers::post_intent))
        .route("/pot/intents/discover", get(pot::handlers::discover_intents))
        .route("/pot/intents/{id}/like", post(pot::handlers::like_intent))
        .route("/pot/intents/{id}/pass", post(pot::handlers::pass_intent))
        .route("/pot/intents/{id}", delete(pot::handlers::withdraw_intent))
        .route("/pot/pots/{id}", get(pot::handlers::get_pot))
        .route("/pot/pots/{id}/route", get(pot::handlers::get_pot_route))
        .route("/routes", get(routes::handlers::list_catalog_routes))
        .route(
            "/routes/{id}/bookings",
            post(routes::handlers::create_catalog_booking),
        )
}