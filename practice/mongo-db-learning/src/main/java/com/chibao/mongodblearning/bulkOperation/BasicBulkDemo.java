package com.chibao.mongodblearning.bulkOperation;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.*;
import org.bson.Document;

import java.util.List;

public class BasicBulkDemo {
    public void executeBulk(MongoCollection<Document> collection) {
        List<WriteModel<Document>> operations = List.of(
                new InsertOneModel<>(new Document("_id", "1").append("status", "ACTIVE")),
                new UpdateOneModel<>(Filters.eq("_id", "2"), Updates.inc("points", 5)),
                new DeleteOneModel<>(Filters.eq("_id", "3"))
        );

        collection.bulkWrite(operations, new BulkWriteOptions().ordered(false));
    }
}
