package com.chibao.japlearning.oneToManyRelationship;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;

@Entity
public class CartItem {
    @Id
    private Long id;

    @ManyToOne
    @JoinColumn(name = "cart_id" , nullable=false)
    private Cart cart;
}
