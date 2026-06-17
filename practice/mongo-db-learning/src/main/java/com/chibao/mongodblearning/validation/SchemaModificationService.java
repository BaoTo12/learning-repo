package com.chibao.mongodblearning.validation;

import com.mongodb.client.MongoDatabase;
import org.bson.Document;

public class SchemaModificationService {
    public void addRequiredField(MongoDatabase database, String collectionName, Document newJsonSchema) {
        // Construct the collMod administration command document
        Document collModCmd = new Document("collMod", collectionName)
                .append("validator", new Document("$jsonSchema", newJsonSchema))
                .append("validationLevel", "strict")
                .append("validationAction", "error");

        // Execute the command against the admin database context
        Document result = database.runCommand(collModCmd);
        System.out.println("collMod execution result: " + result.toJson());
    }
}
