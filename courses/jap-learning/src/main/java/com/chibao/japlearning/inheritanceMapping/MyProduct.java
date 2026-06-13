package com.chibao.japlearning.inheritanceMapping;

import jakarta.persistence.*;

@Entity
@Inheritance(strategy = InheritanceType.SINGLE_TABLE)
@DiscriminatorColumn(
        name = "product_type",
        discriminatorType = DiscriminatorType.INTEGER
)
public class MyProduct {
    @Id
    private long productId;
    private String name;
}

@Entity
@DiscriminatorValue("1")
class Book extends MyProduct {
    private String author;
}

@Entity
@DiscriminatorValue("2")
class Pen extends MyProduct {
    private String color;
}
