use serde::{Deserialize, Serialize};

use crate::shared_kernel::ids::{MatchId, RideIntentId};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MatchStatus {
    Pending,
    Mutual,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MatchRecord {
    id: MatchId,
    from_intent_id: RideIntentId,
    to_intent_id: RideIntentId,
    status: MatchStatus,
}

impl MatchRecord {
    pub fn like(from_intent_id: RideIntentId, to_intent_id: RideIntentId) -> Result<Self, &'static str> {
        if from_intent_id == to_intent_id {
            return Err("cannot like own intent");
        }
        Ok(Self {
            id: MatchId::new(),
            from_intent_id,
            to_intent_id,
            status: MatchStatus::Pending,
        })
    }

    pub fn with_mutual_status(mut self) -> Self {
        self.status = MatchStatus::Mutual;
        self
    }

    pub fn is_mutual(&self) -> bool {
        self.status == MatchStatus::Mutual
    }

    pub fn from_intent_id(&self) -> RideIntentId {
        self.from_intent_id
    }

    pub fn to_intent_id(&self) -> RideIntentId {
        self.to_intent_id
    }

    pub fn reverse_pair(&self) -> (RideIntentId, RideIntentId) {
        (self.to_intent_id, self.from_intent_id)
    }
}

pub fn find_mutual(
    new_like: &MatchRecord,
    existing: &[MatchRecord],
) -> Option<MatchRecord> {
    let (a, b) = new_like.reverse_pair();
    existing.iter().find(|m| {
        m.from_intent_id == a
            && m.to_intent_id == b
            && m.status == MatchStatus::Pending
    })?;
    Some(new_like.clone().with_mutual_status())
}