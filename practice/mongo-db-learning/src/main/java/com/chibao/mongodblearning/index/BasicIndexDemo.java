package com.chibao.mongodblearning.index;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.IndexOptions;
import com.mongodb.client.model.Indexes;
import org.bson.Document;

public class BasicIndexDemo {
    public void configureIndex(MongoCollection<Document> collection) {
        collection.createIndex(
                Indexes.ascending("email"),
                new IndexOptions().name("idx_email").unique(true)
        );

        // 1. Single Field Index
        collection.createIndex(Indexes.ascending("username"));

        // 2. Unique Index (Forces database-level uniqueness)
        collection.createIndex(
                Indexes.ascending("email"),
                new IndexOptions().name("idx_unique_email").unique(true)
        );

        // 3. Compound Index (Multi-key fields with sorting directives)
        // Order: department (ascending) -> age (descending)
        collection.createIndex(
                Indexes.compoundIndex(
                        Indexes.ascending("department"),
                        Indexes.descending("age")
                ),
                new IndexOptions().name("idx_dept_age")
        );
    }
}
