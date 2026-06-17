package com.chibao.mongodblearning.crud;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Projections;
import com.mongodb.client.model.Sorts;
import org.bson.Document;
import org.bson.conversions.Bson;

import java.util.ArrayList;
import java.util.List;

public class QueryModificationsDemo {
    public void run(MongoCollection<Document> collection) {
        Bson projection = Projections.fields(
                Projections.include("name", "email"),
                Projections.excludeId()
        );

        // Sorting: descending order of score, then ascending order of name
        Bson sort = Sorts.orderBy(
                Sorts.descending("score"),
                Sorts.ascending("name")
        );

        // Limit & Skip
        List<Document> results = collection.find(Filters.eq("status", "ACTIVE"))
                .projection(projection)
                .sort(sort)
                .skip(10)  // Skip first 10 documents
                .limit(5)  // Retrieve next 5 documents
                .into(new ArrayList<>());

    }
}
