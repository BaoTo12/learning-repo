package com.chibao.japlearning.jpaEntities;


import jakarta.persistence.*;
import jakarta.validation.constraints.Size;
import org.hibernate.validator.constraints.Length;

@Entity
public class Course {
    @Basic
    @Id
    private int id;

    @Basic(optional = false, fetch = FetchType.LAZY)
    @Size(min = 3, max = 15)
    @Length(min = 3, max = 15)
    @Column(length = 255)
    private String name;
}
