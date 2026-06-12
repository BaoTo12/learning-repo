package com.chibao.japlearning.jpaEntities;

import jakarta.persistence.*;
import org.hibernate.annotations.EmbeddedColumnNaming;

@Entity
public class Company {

    @Id
    @GeneratedValue
    private Integer id;

    private String name;

    private String address;

    private String phone;

    @Embedded
    // By default, Hibernate prefixes the embedded columns with the name of the embedded field.
    // For example, for the embedded field contactPerson, columns would be named like contactPerson_firstName,
    // contactPerson_lastName, etc.
    @EmbeddedColumnNaming("contact_")
    @AttributeOverrides({
            @AttributeOverride(name = "firstName", column = @Column(name = "contact_first_name")),
            @AttributeOverride( name = "lastName", column = @Column(name = "contact_last_name")),
            @AttributeOverride( name = "phone", column = @Column(name = "contact_phone"))
    })
    private ContactPerson contactPerson;

    // standard getters, setters
}