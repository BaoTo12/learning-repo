package com.chibao.mongodblearning.crud;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.UpdateOptions;
import com.mongodb.client.model.Updates;
import com.mongodb.client.result.UpdateResult;
import org.bson.Document;
import org.bson.conversions.Bson;

import java.util.List;

public class ArrayUpdatesDemo {
    public void run(MongoCollection<Document> collection) {
        // 1. Basic Positional Operator ($)
        // Query must target the array element we want to modify.
        var queryFilter = Filters.and(
                Filters.eq("_id", "STD-402"),
                Filters.eq("enrollments.courseCode", "MATH")
        );

        var updateOperation = Updates.set("enrollment.$.status", "COMPLETED");
        collection.updateOne(queryFilter, updateOperation);

        // 2. Filtered Positional Operator ($[identifier]) & arrayFilters
        // Allows updating multiple elements or elements without query filter matching.

        Bson filters = Filters.eq("_id", "STD-402");
        Bson update = Updates.set("enrollment.$[e].score", 100.0);
        List<Document> arrayFilters = List.of(
                new Document("e.courseCode", "MATH").append("e.score", new Document("$lt", 100.0))
        );
        UpdateOptions options = new UpdateOptions().arrayFilters(arrayFilters);
        collection.updateMany(filters, update, options);

        var filter = Filters.eq("sku", "PROD-X-99");
        var update1 = Updates.combine(
                Updates.set("price", 49.99),
                Updates.inc("stock", 5)
        );

        UpdateOptions options1 = new UpdateOptions().upsert(true);
        UpdateResult result = collection.updateOne(filter, update1, options1);

        System.out.println("Matched: " + result.getMatchedCount());
        System.out.println("Modified: " + result.getModifiedCount());
        if (result.getUpsertedId() != null) {
            System.out.println("Inserted brand new document with ID: " + result.getUpsertedId());
        }
    }
}
