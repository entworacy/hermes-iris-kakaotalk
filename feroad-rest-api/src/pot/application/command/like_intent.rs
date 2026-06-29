use crate::infrastructure::app_state::AppState;
use crate::pot::domain::model::match_record::{find_mutual, MatchRecord};
use crate::pot::domain::model::pot::Pot;
use crate::shared_kernel::domain_event::StoredEvent;
use crate::shared_kernel::event_types;
use crate::shared_kernel::ids::RideIntentId;

pub async fn handle(
    state: &AppState,
    from_intent_id: RideIntentId,
    to_intent_id: RideIntentId,
) -> Result<Vec<StoredEvent>, String> {
    let from = state
        .intents
        .read()
        .unwrap()
        .get(&from_intent_id)
        .cloned()
        .ok_or("from intent not found")?;
    let to = state
        .intents
        .read()
        .unwrap()
        .get(&to_intent_id)
        .cloned()
        .ok_or("to intent not found")?;

    if !from.can_receive_like() || !to.can_receive_like() {
        return Err("intent cannot receive like".into());
    }

    let like = MatchRecord::like(from_intent_id, to_intent_id).map_err(|e| e.to_string())?;
    let existing = state.matches.read().unwrap().clone();

    let mut events = vec![StoredEvent::new(
        event_types::INTENT_LIKED,
        format!("{from_intent_id}->{to_intent_id}"),
        from_intent_id.to_string(),
    )];

    state.matches.write().unwrap().push(like.clone());

    if let Some(mutual) = find_mutual(&like, &existing) {
        state.matches.write().unwrap().push(mutual.clone());
        events.push(StoredEvent::new(
            event_types::MUTUAL_MATCH_FORMED,
            format!("{}:{}", mutual.from_intent_id(), mutual.to_intent_id()),
            mutual.from_intent_id().to_string(),
        ));

        let from_intent = state
            .intents
            .read()
            .unwrap()
            .get(&from_intent_id)
            .cloned()
            .ok_or("from intent missing")?;
        let to_intent = state
            .intents
            .read()
            .unwrap()
            .get(&to_intent_id)
            .cloned()
            .ok_or("to intent missing")?;

        let (pot, pot_events) =
            Pot::create_from_intents(&[from_intent.clone(), to_intent.clone()])
                .map_err(|e| e.to_string())?;

        let pot_id = pot.id();
        state.pots.write().unwrap().insert(pot_id, pot);

        {
            let mut intents = state.intents.write().unwrap();
            if let Some(i) = intents.get_mut(&from_intent_id) {
                i.mark_matched(pot_id);
            }
            if let Some(i) = intents.get_mut(&to_intent_id) {
                i.mark_matched(pot_id);
            }
        }

        events.extend(pot_events);
    }

    state.push_events(events.clone());
    Ok(events)
}