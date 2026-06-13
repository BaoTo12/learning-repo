package com.chibao.japlearning.jpaEntities;

import jakarta.persistence.*;

import java.time.LocalDate;

@Entity(name="student")
@Table(name="STUDENT", schema="SCHOOL")
public class Student {
    @Id
    @GeneratedValue(strategy= GenerationType.AUTO)
    private Long id;

    @Column(name="STUDENT_NAME", length=50, nullable=false, unique=false)
    private String name;

    @Transient
    private Integer age;

    private LocalDate birthDate;

    @Enumerated(EnumType.STRING)
    private Gender gender;

    // getters and setters
}
