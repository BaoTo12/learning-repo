package com.chibao.mongodblearning.crud;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.MongoCursor;
import com.mongodb.client.model.Filters;
import org.bson.Document;

import java.util.ArrayList;
import java.util.List;

public class ReadOperationDemo {
    public void run(MongoCollection<Document> collection) {
        Document firstMatch = collection.find(Filters.eq("status", "ACTIVE")).first();
        // Iterate and fetch all matching documents (Try-with-resources avoids cursor leaks)
        List<Document> activeUsers = new ArrayList<>();
        try (MongoCursor<Document> cursor = collection.find(Filters.eq("status", "ACTIVE")).iterator()){
            while (cursor.hasNext()) {
                activeUsers.add(cursor.next());
            }
        }
        // Direct ingestion into list using .into()
        List<Document> allUsers = collection.find().into(new ArrayList<>());
    }
}
