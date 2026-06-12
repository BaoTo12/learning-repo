package com.chibao.japlearning.derivedIdentifier;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.MapsId;
import jakarta.persistence.OneToOne;

@Entity
public class UserProfile {
    @Id
    private Long profileId;

    @OneToOne
    @MapsId
    private User user;
}
