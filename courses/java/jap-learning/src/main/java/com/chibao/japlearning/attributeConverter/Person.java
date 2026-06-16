package com.chibao.japlearning.attributeConverter;

import jakarta.persistence.Convert;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;

@Entity(name = "PersonTable")
public class Person {
    @Id
    private Long id;

    @Convert(converter = PersonNameConverter.class)
    private PersonName personName;

    //...
}
