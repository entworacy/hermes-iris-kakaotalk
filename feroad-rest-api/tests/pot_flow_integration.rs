use chrono::NaiveDate;
use feroad_rest_api::infrastructure::app_state::AppState;
use feroad_rest_api::pot::application::command::like_intent;
use feroad_rest_api::pot::application::command::post_ride_intent::PostRideIntentCommand;
use feroad_rest_api::pot::application::command::post_ride_intent;
use feroad_rest_api::pot::domain::model::pot::PotStatus;
use feroad_rest_api::shared_kernel::ids::UserId;
use feroad_rest_api::shared_kernel::value_objects::{GeoPoint, ServiceDate};
use feroad_rest_api::contract::domain::model::brokerage_contract::BrokerageType;
use feroad_rest_api::booking::domain::model::booking::BookingStatus;

fn sample_cmd(user_id: UserId, hour: u32, minute: u32) -> PostRideIntentCommand {
    PostRideIntentCommand {
        user_id,
        origin: GeoPoint::new(37.5665, 126.9780).unwrap(),
        destination: GeoPoint::new(37.5700, 126.9820).unwrap(),
        service_date: ServiceDate::new(NaiveDate::from_ymd_opt(2026, 7, 1).unwrap()),
        departure_time: chrono::NaiveTime::from_hms_opt(hour, minute, 0).unwrap(),
        passenger_count: 1,
        corporate_org_id: None,
    }
}

#[tokio::test]
async fn pot_flow_creates_ephemeral_route_booking_and_contract() {
    let state = AppState::new();
    let user_a = UserId::new();
    let user_b = UserId::new();
    state.acl.seed_active_user(user_a);
    state.acl.seed_active_user(user_b);

    let intent_a = post_ride_intent::handle(&state, sample_cmd(user_a, 8, 0))
        .await
        .unwrap();
    let intent_b = post_ride_intent::handle(&state, sample_cmd(user_b, 8, 10))
        .await
        .unwrap();

    like_intent::handle(&state, intent_a.id(), intent_b.id())
        .await
        .unwrap();
    like_intent::handle(&state, intent_b.id(), intent_a.id())
        .await
        .unwrap();

    state.dispatch_pending_events().await.unwrap();

    let pot = state.pots.read().unwrap().values().next().unwrap().clone();
    assert_eq!(pot.status(), PotStatus::Converted);
    assert!(pot.route_id().is_some());

    let routes: Vec<_> = state.routes.read().unwrap().values().cloned().collect();
    assert_eq!(routes.len(), 1);
    assert!(routes[0].pot_id().is_some());

    let bookings: Vec<_> = state.bookings.read().unwrap().values().cloned().collect();
    assert_eq!(bookings.len(), 2);
    assert!(bookings.iter().all(|b| b.status() == BookingStatus::Confirmed));

    let contracts: Vec<_> = state.contracts.read().unwrap().values().cloned().collect();
    assert_eq!(contracts.len(), 2);
    assert!(contracts
        .iter()
        .all(|c| c.brokerage_type() == BrokerageType::PotEphemeral));
}