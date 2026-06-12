package com.chibao.japlearning.oneToManyRelationship;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;

import java.util.List;

@Entity
public class Cart {
    @Id
    private Long id;

    @OneToMany(mappedBy = "cart")
    private List<CartItem> items;
}
