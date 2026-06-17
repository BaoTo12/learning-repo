package com.chibao.mongodblearning.validation;

import com.mongodb.client.MongoDatabase;
import com.mongodb.client.model.CreateCollectionOptions;
import com.mongodb.client.model.ValidationAction;
import com.mongodb.client.model.ValidationLevel;
import com.mongodb.client.model.ValidationOptions;
import org.bson.Document;

import java.util.List;

public class BasicValidationDemo {
    public void configureValidation(MongoDatabase database) {
        Document jsonSchema = new Document("bsonType", "object")
                .append("required", List.of("sku", "price"))
                .append("properties", new Document()
                        .append("sku", new Document("bsonType", "string"))
                        .append("price", new Document("bsonType", "double").append("minimum", 0.0))
                );

        ValidationOptions validationOptions = new ValidationOptions()
                .validator(new Document("$jsonSchema", jsonSchema))
                .validationAction(ValidationAction.ERROR)
                .validationLevel(ValidationLevel.STRICT);

        CreateCollectionOptions options = new CreateCollectionOptions().validationOptions(validationOptions);

        database.createCollection("products", options);
    }
}
