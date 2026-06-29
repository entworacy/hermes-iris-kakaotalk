use feroad_rest_api::booking::application::command::request_catalog_booking;
use feroad_rest_api::contract::domain::model::brokerage_contract::BrokerageType;
use feroad_rest_api::infrastructure::app_state::AppState;
use feroad_rest_api::organization::domain::model::organization::{Organization, OrganizationType};
use feroad_rest_api::shared_kernel::ids::UserId;
use feroad_rest_api::shared_kernel::value_objects::{GeoPoint, ServiceDate};
use feroad_rest_api::supply::application::command::activate_catalog_route;
use feroad_rest_api::supply::domain::model::route::Route;
use chrono::NaiveDate;

#[tokio::test]
async fn catalog_booking_creates_contract() {
    let state = AppState::new();
    let rider = UserId::new();
    state.acl.seed_active_user(rider);

    let org = Organization::new(OrganizationType::Operator).verify();
    state.acl.seed_verified_operator(org.id());

    let mut route = Route::new_catalog_fixed(org.id(), "commute");
    route.add_stop(
        feroad_rest_api::supply::domain::model::route::StopType::Pickup,
        GeoPoint::new(37.5, 127.0).unwrap(),
        "A",
    );
    route.add_schedule(
        ServiceDate::new(NaiveDate::from_ymd_opt(2026, 7, 1).unwrap()),
        chrono::NaiveTime::from_hms_opt(8, 0, 0).unwrap(),
    );
    let route_id = route.id();
    state.routes.write().unwrap().insert(route_id, route);

    activate_catalog_route::handle(&state, route_id)
        .await
        .unwrap();

    let booking = request_catalog_booking::handle(&state, rider, route_id)
        .await
        .unwrap();

    state.dispatch_pending_events().await.unwrap();

    let contracts: Vec<_> = state.contracts.read().unwrap().values().cloned().collect();
    assert_eq!(contracts.len(), 1);
    assert_eq!(contracts[0].booking_id(), booking.id());
    assert_eq!(contracts[0].brokerage_type(), BrokerageType::Catalog);
}