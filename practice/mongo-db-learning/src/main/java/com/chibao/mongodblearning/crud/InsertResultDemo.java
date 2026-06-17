package com.chibao.mongodblearning.crud;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.result.InsertManyResult;
import com.mongodb.client.result.InsertOneResult;
import org.bson.BsonValue;
import org.bson.Document;

import java.util.List;
import java.util.Map;

public class InsertResultDemo {
    public void run (MongoCollection<Document> collection){
        // Retrieve single insert ID
        InsertOneResult resultOne = collection.insertOne(new Document("name", "Tom"));
        BsonValue insertedId = resultOne.getInsertedId();
        assert insertedId != null;
        System.out.println("Inserted Single ID: " + insertedId.asObjectId().getValue());

        // Retrieve bulk insert IDs
        List<Document> docs = List.of(new Document("name", "Jerry"), new Document("name", "Spike"));
        InsertManyResult resultMany = collection.insertMany(docs);
        Map<Integer, BsonValue> insertedIds = resultMany.getInsertedIds();
        insertedIds.forEach((index, id) -> {
            System.out.println("Doc at index " + index + " got ID: " + id);
        });
    }
}
