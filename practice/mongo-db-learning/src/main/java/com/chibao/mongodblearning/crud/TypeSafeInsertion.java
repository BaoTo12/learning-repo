package com.chibao.mongodblearning.crud;

import com.mongodb.client.MongoCollection;
import org.bson.Document;
import org.bson.types.Decimal128;

import java.math.BigDecimal;
import java.util.Date;
import java.util.List;

public class TypeSafeInsertion {
    public void insertProduct(MongoCollection<Document> collection) {
        // Robust Pattern: Currency uses BigDecimal wrapped in Decimal128.
        // Stock uses standard Integer (mapping to BSON Int32).
        // Registration timestamp uses Date (mapping to UTC DateTime).
        BigDecimal cost = new BigDecimal("19.99");

        Document product = new Document("_id", new org.bson.types.ObjectId())
                .append("sku", "P-100")
                .append("cost", new Decimal128(cost))
                .append("stock", 150)
                .append("tags", List.of("electronics", "accessories"))
                .append("registeredAt", new Date())
                .append("inStock", true);

        collection.insertOne(product);
        System.out.println("Type-safe document inserted.");
    }
}
