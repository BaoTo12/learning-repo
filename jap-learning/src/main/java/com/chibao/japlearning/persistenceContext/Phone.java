package com.chibao.japlearning.persistenceContext;

import jakarta.persistence.Embeddable;

@Embeddable
public class Phone {
    private String type;
    private String areaCode;
    private String number;

    // standard constructors, getters, and setters
}