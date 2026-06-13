package com.chibao.japlearning.jpaEntities;

import jakarta.persistence.Embeddable;

@Embeddable
public class ContactPerson {

    private String firstName;

    private String lastName;

    private String phone;

    // standard getters, setters
}
