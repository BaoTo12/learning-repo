package com.chibao.japlearning.inheritanceMapping;

import jakarta.persistence.Entity;

@Entity
public class MyEmployee extends Person {
    private String company;
}
