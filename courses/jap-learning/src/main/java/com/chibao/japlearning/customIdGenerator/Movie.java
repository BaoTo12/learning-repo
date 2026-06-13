package com.chibao.japlearning.customIdGenerator;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;

@Entity
public class Movie {
    @Id
    @MovieGeneratedId
    private Long id;

    private String title;
    private String director;
}