use serde::{Deserialize, Serialize};

use crate::shared_kernel::ids::UserId;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum UserStatus {
    Pending,
    Active,
    Suspended,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct User {
    id: UserId,
    status: UserStatus,
}

impl User {
    pub fn register() -> Self {
        Self {
            id: UserId::new(),
            status: UserStatus::Pending,
        }
    }

    pub fn activate(mut self) -> Self {
        self.status = UserStatus::Active;
        self
    }

    pub fn id(&self) -> UserId {
        self.id
    }

    pub fn status(&self) -> UserStatus {
        self.status
    }

    pub fn is_active(&self) -> bool {
        self.status == UserStatus::Active
    }
}