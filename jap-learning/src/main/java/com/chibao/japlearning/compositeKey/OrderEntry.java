package com.chibao.japlearning.compositeKey;

import jakarta.persistence.EmbeddedId;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;

@Entity
@IdClass(OrderEntryPK.class)
public class OrderEntry {
    @EmbeddedId
    private OrderEntryPK orderEntryPK;

    @Id
    private long orderId;
    @Id
    private long productId;
}
